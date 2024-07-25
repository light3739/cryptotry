import asyncio
import configparser
import json
import logging
import os
import time
import traceback

from pynput import keyboard

from undetected import UndetectedSetup

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка конфигурации
config = configparser.ConfigParser()
config.read('config.ini')
DEFAULT_TIMEOUT = int(config.get('Timeouts', 'default', fallback=10))
LONG_TIMEOUT = int(config.get('Timeouts', 'long', fallback=30))


class UserActionListener:
    def __init__(self):
        self.actions = []
        self.last_url = None
        self.main_window = None
        self.keyboard_listener = None
        self.window_size = None

    def start_listeners(self):
        self.start_keyboard_listener()

    def stop_listeners(self):
        self.stop_keyboard_listener()

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

    async def inject_event_listeners(self, tab):
        js_code = """
        if (typeof window.nodriverActions === 'undefined') {
            window.nodriverActions = [];
        }
    
        window.nodriverClickListener = function(e) {
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
            window.nodriverActions.push(data);
        };
    
        window.nodriverInputListener = function(e) {
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
            window.nodriverActions.push(data);
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
    
        if (!window.nodriverActionsInjected) {
            document.addEventListener('click', window.nodriverClickListener, true);
            document.addEventListener('input', window.nodriverInputListener, true);
            window.nodriverActionsInjected = true;
        }
        """
        await tab.evaluate(js_code)

    async def get_actions_from_js(self, tab):
        js_actions = await tab.evaluate("window.nodriverActions")
        if js_actions:
            self.actions.extend(js_actions)
            await tab.evaluate("window.nodriverActions = []")


import re


async def get_page_title(tab):
    content = await tab.get_content()
    match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
    if match:
        return match.group(1)
    return "Untitled"


async def monitor_url_and_actions(browser, listener, stop_event):
    main_tab = browser.main_tab
    listener.main_window = main_tab
    while not stop_event.is_set():
        try:
            current_url = main_tab.url
            if current_url != listener.last_url:
                listener.actions.append({
                    "type": "url_change",
                    "url": current_url,
                    "time": time.time(),
                    "previous_url": listener.last_url
                })
                listener.last_url = current_url
                await listener.inject_event_listeners(main_tab)

            await listener.get_actions_from_js(main_tab)

            page_state = await main_tab.evaluate("document.readyState")
            if page_state != "complete":
                logger.info(f"Page is still loading. Current state: {page_state}")

            window_id, bounds = await main_tab.get_window()
            title = await get_page_title(main_tab)
            listener.actions.append({
                "type": "page_info",
                "url": current_url,
                "title": title,
                "time": time.time(),
                "window_id": window_id,
                "window_bounds": {
                    "left": bounds.left,
                    "top": bounds.top,
                    "width": bounds.width,
                    "height": bounds.height
                }
            })

        except Exception as e:
            logger.error(f"Error in monitoring thread: {str(e)}")
            logger.error(traceback.format_exc())

        await asyncio.sleep(0.5)

    logger.info("Monitoring thread has stopped.")


async def record_actions(setup):
    listener = UserActionListener()
    stop_event = asyncio.Event()

    try:
        main_tab = setup.browser.main_tab

        await main_tab.get("https://miles.plumenetwork.xyz/")
        listener.last_url = main_tab.url

        print("Recording started. Perform your actions.")
        print("Press Ctrl+C to stop recording.")

        listener.start_listeners()
        monitor_task = asyncio.create_task(monitor_url_and_actions(setup.browser, listener, stop_event))

        try:
            while not stop_event.is_set():
                # Получаем события кликов
                click_events = await get_click_events(main_tab)
                if click_events:
                    listener.actions.extend(click_events)
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Recording stopped by user.")
        finally:
            stop_event.set()
            listener.stop_listeners()
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
        elif action['type'] == 'key_press':
            playback_actions.append({
                'type': 'key_press',
                'key': action['key']
            })
        elif action['type'] == 'url_change':
            playback_actions.append({
                'type': 'navigate',
                'url': action['url']
            })
    return playback_actions


async def inject_click_listener(tab):
    js_code = """
    if (typeof window.clickEvents === 'undefined') {
        window.clickEvents = [];
    }

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

    document.addEventListener('click', function(e) {
        var element = e.target;
        var eventData = {
            type: 'click',
            tagName: element.tagName,
            id: element.id,
            className: element.className,
            xpath: getXPath(element),
            time: new Date().getTime()
        };
        window.clickEvents.push(eventData);
    }, true);
    """
    await tab.evaluate(js_code)


async def get_click_events(tab):
    events = await tab.evaluate("window.clickEvents")
    if events:
        await tab.evaluate("window.clickEvents = []")
    return events


async def monitor_clicks(tab):
    await inject_click_listener(tab)
    while True:
        events = await get_click_events(tab)
        if events:
            for event in events:
                print(f"Click event: {event}")
        await asyncio.sleep(0.5)


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

        # Создаем задачу для мониторинга кликов
        click_monitor_task = asyncio.create_task(monitor_clicks(setup.browser.main_tab))

        # Запускаем запись действий
        await record_actions(setup)

        # Останавливаем мониторинг кликов
        click_monitor_task.cancel()
        try:
            await click_monitor_task
        except asyncio.CancelledError:
            pass

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
    asyncio.run(main())
