import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

import undetected_chromedriver as uc
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


def random_sleep(min_seconds=1, max_seconds=5):
    time.sleep(random.randint(min_seconds * 1000, max_seconds * 1000) / 1000)


def simulate_human_behavior(driver):
    window_width = driver.execute_script("return window.innerWidth;")
    window_height = driver.execute_script("return window.innerHeight;")
    num_movements = random.randint(1, 5)

    for i in range(num_movements):
        target_x = random.randint(0, window_width)
        target_y = random.randint(0, window_height)
        driver.execute_script(f"""
            var event = new MouseEvent('mousemove', {{
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': {target_x},
                'clientY': {target_y}
            }});
            document.dispatchEvent(event);
        """)

        sleep_time = random.randint(1000, 2000) / 1000
        random_sleep(1, 2)

    scroll_y = random.randint(100, min(1000, window_height))
    driver.execute_script(f"window.scrollTo(0, {scroll_y});")

    sleep_time = random.randint(1000, 5000) / 1000
    random_sleep()


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
        simulate_human_behavior(driver)
        random_sleep(5, 15)

except KeyboardInterrupt:
    print("\nПрограмма завершена пользователем.")
except Exception as e:
    print(f"Произошла ошибка: {e}")
finally:
    pass
