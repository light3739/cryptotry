import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

import undetected_chromedriver as uc
from selenium.webdriver import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By


def get_random_user_agent():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]
    return random.choice(user_agents)


def create_or_get_profile(profile_name="default"):
    profiles_dir = os.path.join(os.getcwd(), "chrome_profiles")
    profile_path = os.path.join(profiles_dir, profile_name)

    if not os.path.exists(profile_path):
        os.makedirs(profile_path)

    metadata_path = os.path.join(profile_path, "metadata.json")
    if not os.path.exists(metadata_path):
        metadata = {
            "created_at": time.time(),
            "last_used": time.time(),
            "user_agent": get_random_user_agent()
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)
    else:
        with open(metadata_path, "r+") as f:
            metadata = json.load(f)
            metadata["last_used"] = time.time()
            f.seek(0)
            json.dump(metadata, f)
            f.truncate()

    return profile_path, metadata["user_agent"]


def random_sleep(min_milliseconds=1000, max_milliseconds=5000):
    time.sleep(random.randint(min_milliseconds, max_milliseconds) / 1000)


def human_like_mouse_move(driver, start_x, start_y, end_x, end_y):
    steps = random.randint(50, 100)
    for i in range(steps):
        t = i / steps
        x = int(start_x + (end_x - start_x) * (t + random.uniform(-0.1, 0.1)))
        y = int(start_y + (end_y - start_y) * (t + random.uniform(-0.1, 0.1)))
        try:
            driver.execute_script(f"""
                var element = document.elementFromPoint({x}, {y});
                if (element) {{
                    var event = new MouseEvent('mousemove', {{
                        clientX: {x},
                        clientY: {y},
                        bubbles: true
                    }});
                    element.dispatchEvent(event);
                }}
            """)
        except Exception as e:
            print(f"Ошибка при движении мыши: {e}")
        random_sleep(10, 20)  # 10-20 миллисекунд


def random_click(driver):
    clickable_elements = driver.find_elements(By.CSS_SELECTOR, 'a, button, input[type="submit"]')
    if clickable_elements:
        element = random.choice(clickable_elements)
        human_like_mouse_move(driver,
                              random.randint(0, driver.execute_script("return window.innerWidth;")),
                              random.randint(0, driver.execute_script("return window.innerHeight;")),
                              element.location['x'],
                              element.location['y'])
        element.click()
        random_sleep(1, 3)


def simulate_keyboard_input(driver):
    element = driver.find_element(By.TAG_NAME, 'body')
    random_text = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(5, 10)))
    for char in random_text:
        element.send_keys(char)
        random_sleep(100, 300)  # 100-300 миллисекунд
    random_sleep(500, 1500)  # 500-1500 миллисекунд
    for _ in range(len(random_text)):
        element.send_keys(Keys.BACKSPACE)
        random_sleep(100, 300)  # 100-300 миллисекунд


def random_pause():
    if random.random() < 0.1:  # 10% шанс на длительную паузу
        random_sleep(5000, 15000)  # 5-15 секунд
    else:
        random_sleep(500, 2000)  # 0.5-2 секунды


def add_random_headers(driver):
    headers = {
        'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': headers})


def simulate_human_behavior(driver):
    try:
        window_width = driver.execute_script("return window.innerWidth;")
        window_height = driver.execute_script("return window.innerHeight;")

        random_pause()

        # Случайное движение мыши
        num_movements = random.randint(1, 5)
        for _ in range(num_movements):
            start_x, start_y = random.randint(0, window_width), random.randint(0, window_height)
            end_x, end_y = random.randint(0, window_width), random.randint(0, window_height)
            human_like_mouse_move(driver, start_x, start_y, end_x, end_y)
            random_pause()

        # Случайный клик
        if random.random() < 0.3:  # 30% шанс на клик
            try:
                random_click(driver)
            except Exception as e:
                print(f"Ошибка при клике: {e}")
            random_pause()

        # Случайный ввод с клавиатуры
        if random.random() < 0.2:  # 20% шанс на ввод с клавиатуры
            try:
                simulate_keyboard_input(driver)
            except Exception as e:
                print(f"Ошибка при вводе с клавиатуры: {e}")
            random_pause()

        # Случайный скролл
        scroll_y = random.randint(100, min(1000, window_height))
        driver.execute_script(f"window.scrollTo(0, {scroll_y});")
        random_pause()

    except Exception as e:
        print(f"Ошибка при симуляции поведения: {e}")


# Получаем путь к профилю и user agent
profile_path, user_agent = create_or_get_profile("my_profile")

options = uc.ChromeOptions()
options.add_argument(f'user-agent={user_agent}')
options.add_argument("--window-size=1366,768")
options.add_argument("--enable-extensions")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-popup-blocking")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument(f"--user-data-dir={profile_path}")
options.add_argument("--profile-directory=Default")
options.add_argument("--lang=de-DE")
options.add_argument("--timezone=Europe/Berlin")

# Дополнительные параметры для маскировки
options.add_argument("--disable-infobars")
options.add_argument("--disable-save-password-bubble")
options.add_argument("--ignore-certificate-errors")

# Создаем экземпляр драйвера
driver = uc.Chrome(options=options)

try:
    driver.set_window_size(1366, 768)

    # Маскировка WebDriver
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Рандомизация WebGL
    driver.execute_script("""
    const getParameter = WebGLRenderingContext.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
      if (parameter === 37445) {
        return 'Intel Open Source Technology Center';
      }
      if (parameter === 37446) {
        return 'Mesa DRI Intel(R) Ivybridge Mobile ';
      }
      return getParameter(parameter);
    };
    """)

    # Устанавливаем немецкое время
    german_time = datetime.now(timezone.utc) + timedelta(hours=1)  # UTC+1 для Германии
    driver.execute_script(
        f"Date.prototype.getTimezoneOffset = function() {{ return -60; }}; Date.now = function() {{ return new Date({german_time.timestamp() * 1000}).getTime(); }};")

    # Открываем страницу
    driver.get("https://www.example.com")
    random_sleep()

    print("Браузер открыт и готов к использованию.")
    print("Нажмите Ctrl+C для завершения программы.")

    while True:
        try:
            simulate_human_behavior(driver)
            random_sleep(5000, 15000)  # 5-15 секунд между итерациями
        except Exception as e:
            print(f"Произошла ошибка в основном цикле: {e}")
            random_sleep(5000, 10000)  # Пауза перед следующей попыткой
        except KeyboardInterrupt:
            print("\nПрограмма завершена пользователем.")
            break
except KeyboardInterrupt:
    print("\nПрограмма завершена пользователем.")
except Exception as e:
    print(f"Произошла ошибка: {e}")
finally:
    pass
