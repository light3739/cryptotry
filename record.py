import asyncio
import atexit
import configparser
import json
import logging
import os
import threading
import time
import traceback
from contextlib import contextmanager
from typing import Tuple, Union

import undetected_chromedriver as uc
from pynput import keyboard
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException, \
    WebDriverException, NoSuchWindowException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.events import EventFiringWebDriver, AbstractEventListener
from selenium.webdriver.support.ui import WebDriverWait

from undetected import UndetectedSetup

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка конфигурации
config = configparser.ConfigParser()
config.read('config.ini')
DEFAULT_TIMEOUT = int(config.get('Timeouts', 'default', fallback=10))
LONG_TIMEOUT = int(config.get('Timeouts', 'long', fallback=30))


class CustomChrome(uc.Chrome):
    def __del__(self):
        try:
            self.service.stop()
        except Exception:
            pass
        try:
            self.quit()
        except Exception:
            pass


class ElementCache:
    def __init__(self):
        self.cache = {}

    def get(self, driver, locator):
        key = str(locator)
        if key not in self.cache:
            self.cache[key] = driver.find_element(*locator)
        return self.cache[key]

    def clear(self):
        self.cache.clear()


element_cache = ElementCache()


class UserActionListener(AbstractEventListener):
    def __init__(self):
        self.actions = []
        self.last_url = None
        self.main_window = None
        self.keyboard_listener = None
        self.window_size = None

    def start_keyboard_listener(self):
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        self.keyboard_listener.start()

    def stop_keyboard_listener(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()

    def on_key_press(self, key):
        try:
            char = key.char
        except AttributeError:
            char = str(key)
        self.actions.append({
            "type": "key_press",
            "key": char,
            "time": time.time()
        })

    def after_navigate_to(self, url, driver):
        self.actions.append({
            "type": "navigated",
            "url": driver.current_url,
            "time": time.time(),
            "title": driver.title
        })
        self.last_url = driver.current_url
        self.inject_event_listeners(driver)
        self.window_size = driver.get_window_size()

    def inject_event_listeners(self, driver):
        js_code = """
        window.seleniumClickListener = function(e) {
            var element = e.target;
            var xpath = getXPath(element);
            var rect = element.getBoundingClientRect();
            var data = {
                type: 'click',
                tagName: element.tagName,
                id: element.id,
                className: element.className,
                href: element.href,
                value: element.value,
                textContent: element.textContent,
                xpath: xpath,
                x: (rect.left + window.scrollX) / window.innerWidth,
                y: (rect.top + window.scrollY) / window.innerHeight,
                time: new Date().getTime()
            };
            window.seleniumActions.push(data);
        };

        window.seleniumInputListener = function(e) {
            var element = e.target;
            var xpath = getXPath(element);
            var rect = element.getBoundingClientRect();
            var data = {
                type: 'input',
                tagName: element.tagName,
                id: element.id,
                className: element.className,
                value: element.value,
                xpath: xpath,
                x: (rect.left + window.scrollX) / window.innerWidth,
                y: (rect.top + window.scrollY) / window.innerHeight,
                time: new Date().getTime()
            };
            window.seleniumActions.push(data);
        };

        function getXPath(element) {
            if (element.id !== '')
                return 'id("' + element.id + '")';
            if (element === document.body)
                return element.tagName;

            var ix = 0;
            var siblings = element.parentNode.childNodes;
            for (var i = 0; i < siblings.length; i++) {
                var sibling = siblings[i];
                if (sibling === element)
                    return getXPath(element.parentNode) + '/' + element.tagName + '[' + (ix + 1) + ']';
                if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                    ix++;
            }
        }

        if (!window.seleniumActionsInjected) {
            window.seleniumActions = [];
            document.addEventListener('click', window.seleniumClickListener, true);
            document.addEventListener('input', window.seleniumInputListener, true);
            window.seleniumActionsInjected = true;
        }
        """
        driver.execute_script(js_code)

    def get_actions_from_js(self, driver):
        js_actions = driver.execute_script("return window.seleniumActions;")
        if js_actions:
            self.actions.extend(js_actions)
            driver.execute_script("window.seleniumActions = [];")


def smart_find_element(driver, locator_dict):
    for method, value in locator_dict.items():
        try:
            if method == 'id':
                return driver.find_element(By.ID, value)
            elif method == 'name':
                return driver.find_element(By.NAME, value)
            elif method == 'class':
                return driver.find_element(By.CLASS_NAME, value)
            elif method == 'xpath':
                return driver.find_element(By.XPATH, value)
            elif method == 'css':
                return driver.find_element(By.CSS_SELECTOR, value)
        except NoSuchElementException:
            continue
    return None


def wait_for_element(driver, locator: Union[Tuple[str, str], Tuple[By, str]], timeout: int = DEFAULT_TIMEOUT):
    try:
        if isinstance(locator[0], str):
            selenium_locator = locator
        else:
            selenium_locator = (locator[0].__str__(), locator[1])

        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(selenium_locator)
        )
    except TimeoutException:
        logger.warning(f"Element {locator} not found within {timeout} seconds")
        return None


def retry_action(func, max_attempts: int = 3, delay: int = 1):
    def wrapper(*args, **kwargs):
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except (StaleElementReferenceException, TimeoutException) as e:
                if attempt == max_attempts - 1:
                    logger.error(f"Action failed after {max_attempts} attempts: {str(e)}")
                    raise
                logger.warning(f"Action failed, retrying in {delay} seconds...")
                time.sleep(delay)

    return wrapper


@contextmanager
def create_driver(setup):
    driver = None
    try:
        driver = setup.get_driver()
        if driver is None:
            setup.initialize_driver()
            driver = setup.get_driver()
        if driver is None:
            raise WebDriverException("Failed to initialize the driver")
        yield driver
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error during driver cleanup: {str(e)}")


def safe_quit(driver):
    try:
        if driver:
            driver.quit()
    except Exception as e:
        logger.error(f"Error during driver cleanup: {str(e)}")


def take_error_screenshot(driver, error_name):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_name = f"error_{error_name}_{timestamp}.png"
    driver.save_screenshot(screenshot_name)
    logger.info(f"Error screenshot saved: {screenshot_name}")


def recover_from_error(driver):
    try:
        driver.refresh()
        WebDriverWait(driver, DEFAULT_TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        logger.info("Page successfully refreshed after error")
    except Exception as e:
        logger.error(f"Failed to recover from error: {str(e)}")


def is_window_handle_valid(driver, handle):
    try:
        driver.switch_to.window(handle)
        return True
    except NoSuchWindowException:
        return False


def safe_switch_window(driver, window_handle):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            if is_window_handle_valid(driver, window_handle):
                driver.switch_to.window(window_handle)
                return True
            else:
                logger.warning(f"Window handle {window_handle} is not valid.")
                return False
        except WebDriverException as e:
            if attempt == max_attempts - 1:
                logger.error(f"Failed to switch to window {window_handle} after {max_attempts} attempts.")
                return False
            logger.warning(f"Failed to switch window, retrying... Error: {e}")
            time.sleep(1)
    return False


@retry_action
def monitor_url_and_actions(ef_driver, listener, stop_event):
    listener.main_window = ef_driver.current_window_handle
    while not stop_event.is_set():
        try:
            current_handles = ef_driver.window_handles
            if len(current_handles) > 1:
                for handle in current_handles:
                    if handle != listener.main_window:
                        safe_switch_window(ef_driver, handle)
                        listener.actions.append({
                            "type": "window_change",
                            "url": ef_driver.current_url,
                            "time": time.time(),
                            "window_handle": handle
                        })
                        listener.inject_event_listeners(ef_driver)
                        break  # Обработаем только первое новое окно

            current_url = ef_driver.current_url
            if current_url != listener.last_url:
                listener.actions.append({
                    "type": "url_change",
                    "url": current_url,
                    "time": time.time(),
                    "previous_url": listener.last_url
                })
                listener.last_url = current_url
                listener.inject_event_listeners(ef_driver)

            listener.get_actions_from_js(ef_driver)

            # Проверяем, существует ли текущее окно
            if ef_driver.current_window_handle not in current_handles:
                logger.info("Current window was closed. Switching to main window.")
                safe_switch_window(ef_driver, listener.main_window)

            page_state = ef_driver.execute_script("return document.readyState;")
            if page_state != "complete":
                logger.info(f"Page is still loading. Current state: {page_state}")

            listener.actions.append({
                "type": "page_info",
                "url": ef_driver.current_url,
                "title": ef_driver.title,
                "time": time.time(),
                "window_size": ef_driver.get_window_size()
            })

        except NoSuchWindowException:
            logger.warning("Browser window has been closed. Switching to main window.")
            if listener.main_window in ef_driver.window_handles:
                safe_switch_window(ef_driver, listener.main_window)
            else:
                logger.error("Main window has been closed. Stopping monitoring.")
                stop_event.set()
                break
        except WebDriverException as e:
            logger.error(f"WebDriver exception occurred: {str(e)}")
            if "invalid session id" in str(e).lower():
                logger.critical("Browser session has ended. Stopping monitoring.")
                stop_event.set()
                break
            take_error_screenshot(ef_driver, "webdriver_exception")
            recover_from_error(ef_driver)
        except Exception as e:
            logger.error(f"Unexpected error in monitoring thread: {str(e)}")
            logger.error(traceback.format_exc())
            take_error_screenshot(ef_driver, "unexpected_error")
            stop_event.set()
            break

        time.sleep(0.5)  # Небольшая задержка для снижения нагрузки на CPU

    logger.info("Monitoring thread has stopped.")


async def record_actions(setup):
    listener = UserActionListener()
    stop_event = asyncio.Event()

    try:
        main_tab = setup.main_tab

        await main_tab.get("https://miles.plumenetwork.xyz/")
        listener.last_url = main_tab.url

        print("Recording started. Perform your actions.")
        print("Press Ctrl+C to stop recording.")

        listener.start_keyboard_listener()
        monitor_task = asyncio.create_task(monitor_url_and_actions(setup.browser, listener, stop_event))

        try:
            while not stop_event.is_set():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Recording stopped by user.")
        finally:
            stop_event.set()
            listener.stop_keyboard_listener()
            await monitor_task

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        with open("recorded_actions.json", "w") as f:
            json.dump(listener.actions, f, indent=2)
        print("Actions recorded and saved to recorded_actions.json")

        playback_actions = export_actions_for_playback(listener.actions)
        with open("playback_actions.json", "w") as f:
            json.dump(playback_actions, f, indent=2)
        print("Playback actions saved to playback_actions.json")


def export_actions_for_playback(actions):
    playback_actions = []
    for action in actions:
        if action['type'] in ['click', 'input']:
            playback_actions.append({
                'type': action['type'],
                'selector': f"xpath:{action['xpath']}",
                'value': action.get('value', '')
            })
    return playback_actions


async def main():
    proxy = {
        'host': '45.13.195.53',
        'port': '30001',
        'user': 'vintarik8_gmail_com',
        'pass': 'c560667e15'
    }
    setup = UndetectedSetup("my_profile", proxy=proxy)
    try:
        await setup.initialize_driver()
        await record_actions(setup)
    except Exception as e:
        logger.error(f"An error occurred in main: {e}")
        logger.error(traceback.format_exc())
    finally:
        if setup.browser:
            await setup.close_browser()
        if hasattr(setup, 'proxy_extension') and setup.proxy_extension:
            try:
                os.remove(setup.proxy_extension)
                logger.info(f"Proxy extension {setup.proxy_extension} removed.")
            except Exception as e:
                logger.error(f"Failed to remove proxy extension: {e}")


if __name__ == "__main__":
    main()
