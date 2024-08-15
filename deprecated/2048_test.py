import zipfile
import threading
import time
import undetected_chromedriver as uc
import os
import shutil
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium_stealth import stealth
import logging

def create_proxy_extension(proxy, index):
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        },
        "minimum_chrome_version": "22.0.0"
    }
    """
    background_js = """
    var config = {
            mode: "fixed_servers",
            rules: {
            singleProxy: {
                scheme: "http",
                host: "%s",
                port: parseInt(%s)
            },
            bypassList: ["localhost"]
            }
        };
    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
    function callbackFn(details) {
        return {
            authCredentials: {
                username: "%s",
                password: "%s"
            }
        };
    }
    chrome.webRequest.onAuthRequired.addListener(
                callbackFn,
                {urls: ["<all_urls>"]},
                ['blocking']
    );
    """ % (proxy['host'], proxy['port'], proxy['user'], proxy['pass'])
    pluginfile = f'proxy_auth_plugin_{index}.zip'
    try:
        with zipfile.ZipFile(pluginfile, 'w') as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        print(f"Создано расширение прокси: {pluginfile}")
    except Exception as e:
        print(f"Ошибка при создании расширения прокси: {e}")
    return pluginfile




def unlock_wallet(driver, password):
    try:
        # Ввод пароля и разблокировка кошелька
        password_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Password']"))
        )
        password_input.send_keys(password)
        unlock_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//span[text()='Unlock']"))
        )
        unlock_button.click()
        print("Кошелек разблокирован")
    except Exception as e:
        print(f"Ошибка при разблокировке кошелька: {e}")



logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def confirm_transaction(driver):
    time.sleep(4)
    try:
        # Поиск окна с URL, содержащим 'popout.html'
        for window in driver.window_handles:
            driver.switch_to.window(window)
            if 'popout.html' in driver.current_url:
                logging.info(f"Переключились на окно расширения: {driver.current_url}")
                break
        else:
            logging.error("Окно с 'popout.html' не найдено")
            return

        # Нажатие кнопки 'Подтвердить'
        try:
            confirm_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Approve']"))
            )
            confirm_button.click()
            time.sleep(2)
            logging.info("Кнопка 'Подтвердить' нажата")
        except Exception as e:
            logging.error(f"Кнопка 'Подтвердить' не кликабельна или не найдена, пробуем через JavaScript. Ошибка: {e}")
            try:
                driver.execute_script("arguments[0].click();", confirm_button)
                logging.info("Кнопка 'Подтвердить' нажата через JavaScript")
            except Exception as js_e:
                logging.error(f"Ошибка при попытке нажать кнопку через JavaScript: {js_e}")

        # Возвращение в основное окно
        driver.switch_to.window(driver.window_handles[0])
        logging.info(f"Вернулись в основное окно: {driver.current_url}")

    except Exception as e:
        logging.error(f"Ошибка при переключении окон: {e}")


def start_game(driver):
    try:
        # Переход на сайт игры
        driver.get("https://fomoney-sonic.io/")
        print("Перешли на сайт игры")

        # Ожидание загрузки страницы и нажатие кнопки "Play"
        play_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Play']"))
        )

        play_button.click()
        print("Нажали кнопку 'Play'")

        while True:
            # Нажатие кнопки "Mint New Game"
            mint_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Mint New Game']"))
            )
            # Эмуляция движения мыши к кнопке "Mint New Game"
            driver.execute_script("""
                var event = new MouseEvent('mousemove', {
                    'view': window,
                    'bubbles': true,
                    'cancelable': true,
                    'clientX': arguments[0].getBoundingClientRect().left + (arguments[0].offsetWidth / 2),
                    'clientY': arguments[0].getBoundingClientRect().top + (arguments[0].offsetHeight / 2)
                });
                arguments[0].dispatchEvent(event);
            """, mint_button)
            time.sleep(1)
            mint_button.click()
            print("Нажали кнопку 'Mint New Game'")
            time.sleep(5)

            # Проверка наличия кнопки "Select Team"
            select_team_button = driver.find_elements(By.XPATH, "//button[text()='Select Team']")
            if select_team_button:
                print("Кнопка 'Select Team' найдена, перезагружаем страницу")
                driver.refresh()
                time.sleep(5)
            else:
                print("Кнопка 'Select Team' не найдена, продолжаем")

                # Подтверждение транзакции в окне расширения
                confirm_transaction(driver)
                break
    except Exception as e:
        print(f"Ошибка при запуске игры: {e}")


def play_game(driver):
    actions = [Keys.UP, Keys.RIGHT]

    # Проверка наличия кнопки "SUBMIT TO LEADERBOARD"
    try:
        submit_button = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH, "//button[@class='submit_bt' and text()='SUBMIT TO LEADERBOARD']")
            )
        )
        print("Кнопка 'SUBMIT TO LEADERBOARD' найдена, начинаем игру")
    except Exception as e:
        print(f"Кнопка 'SUBMIT TO LEADERBOARD' не найдена, ошибка: {e}")
        return

    game_board = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, 'body'))
    )

    def handle_alert_and_refresh(driver):
        try:
            alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert_text = alert.text
            alert.accept()
            print(f"Алерт закрыт с текстом: {alert_text}")
            if "move invalid" in alert_text.lower():
                return "invalid_move"
            return True
        except:
            return False

    def periodic_alert_check(driver, game_board):
        while True:
            alert_result = handle_alert_and_refresh(driver)
            if alert_result == "invalid_move":
                print("Обнаружен алерт 'Move invalid!', делаем ход вниз.")
                game_board.send_keys(Keys.DOWN)
                time.sleep(0.5)
                confirm_transaction(driver)
                if handle_alert_and_refresh(driver) == "invalid_move":
                    print("Обнаружен алерт 'Move invalid!' после хода вниз, делаем ход влево.")
                    game_board.send_keys(Keys.LEFT)
                    confirm_transaction(driver)
            time.sleep(0.5)

    alert_thread = threading.Thread(target=periodic_alert_check, args=(driver, game_board))
    alert_thread.start()

    while True:
        try:
            for action in actions:
                print(f"Делаем ход: {action}")
                game_board.send_keys(action)
                confirm_transaction(driver)
        except Exception as e:
            print(f"Ошибка во время игры: {e}")
            if handle_alert_and_refresh(driver):
                confirm_transaction(driver)
                continue



# ...




def run_browser_instance(proxy, user_agent, user_data_dir, password, index):
    try:
        options = uc.ChromeOptions()
        pluginfile = create_proxy_extension(proxy, index)
        options.add_extension(pluginfile)

        options.add_argument(f'--user-data-dir={user_data_dir}')
        options.add_argument(f'--profile-directory=Profile{index}')
        options.add_argument("--disable-notifications")
        options.add_argument("--mute-audio")
        options.add_argument(f"user-agent={user_agent}")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-first-run")
        options.add_argument("--no-service-autorun")
        options.add_argument("--password-store=basic")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--start-maximized")
        options.add_argument("--lang=de-DE")
        options.add_argument("--timezone=Europe/Berlin")
        options.add_argument("--headless")  # Добавляем Headless Mode

        chromedriver_path = f'C:\\Users\\Саня\\appdata\\roaming\\undetected_chromedriver\\undetected_chromedriver.exe'

        print(f"Запуск браузера с chromedriver по пути: {chromedriver_path}")
        driver = uc.Chrome(options=options, driver_executable_path=chromedriver_path)
        print(f"Браузер {index + 1} успешно запущен")

        # Применение selenium-stealth для маскировки браузера
        stealth(driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True)

        driver.get("chrome-extension://aflkmfhebedbjioipglgcbcmnbpgliof/popup.html#/unlock")
        print(f"Браузер {index + 1}: Открыта страница расширения")

        unlock_wallet(driver, password)
        start_game(driver)
        play_game(driver)

        input(f"Браузер {index + 1}: Нажмите Enter для завершения работы и закрытия браузера...")

    except Exception as e:
        print(f"Ошибка в браузере {index + 1}: {e}")

    finally:
        try:
            driver.quit()
            print(f"Браузер {index + 1} закрыт")
        except UnboundLocalError:
            print(f"Не удалось закрыть браузер {index + 1}, так как он не был запущен.")














if __name__ == "__main__":
    proxies = [
        {'host': '213.232.118.183', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '213.232.117.163', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '213.232.116.16', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '83.171.241.127', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '213.232.118.183', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '213.232.118.48', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '45.13.194.63', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '213.232.119.91', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '213.232.117.246', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '45.13.194.92', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'},
        {'host': '45.13.194.92', 'port': 30001, 'user': 'wereise15609_gmail_com', 'pass': 'f66f2c4d64'}
    ]
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, как Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, как Gecko) Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, как Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, как Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, как Gecko) Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, как Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, как Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, как Gecko) Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, как Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, как Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, как Gecko) Chrome/91.0.4472.124 Safari/537.36"
    ]
    user_data_dirs = [
        r'C:\Users\Саня\Desktop\2',
        r'C:\Users\Саня\Desktop\3',
        r'C:\Users\Саня\Desktop\4',
        r'C:\Users\Саня\Desktop\5',
        r'C:\Users\Саня\Desktop\6',
        r'C:\Users\Саня\Desktop\7',
        r'C:\Users\Саня\Desktop\8',
        r'C:\Users\Саня\Desktop\9',
        r'C:\Users\Саня\Desktop\10',
        r'C:\Users\Саня\Desktop\11',
        r'C:\Users\Саня\Desktop\main'
    ]
    password = "Arsenal15609"

    choices = []

    # Сбор ответов пользователя
    for i in range(len(proxies)):
        choice = input(f"Запустить браузер {i + 2}? (y/n): ").strip().lower()
        choices.append(choice)

    # Использование ThreadPoolExecutor для управления потоками
    with ThreadPoolExecutor(max_workers=len(proxies)) as executor:
        futures = []
        for i in range(len(proxies)):
            if choices[i] == 'y':
                futures.append(executor.submit(run_browser_instance, proxies[i], user_agents[i], user_data_dirs[i], password, i))

        # Обработка завершения потоков
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Ошибка в потоке: {e}")

