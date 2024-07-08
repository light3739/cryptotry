import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import os
import json

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

# Создаем экземпляр драйвера
driver = uc.Chrome(options=options)

try:
    # Устанавливаем размер окна
    driver.set_window_size(1366, 768)

    # Дополнительные настройки для маскировки
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Проверяем User-Agent
    driver.get("https://www.whatismybrowser.com/detect/what-is-my-user-agent/")
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "detected_value")))
    detected_user_agent = driver.find_element(By.ID, "detected_value").text
    print(f"Detected User-Agent: {detected_user_agent}")

    # Эмуляция действий реального пользователя
    driver.get("https://bot.sannysoft.com/")

    # Ожидаем загрузки страницы
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    # Эмуляция скролла
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    # Скролл обратно вверх
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)

    # Эмуляция движения мыши
    driver.execute_script("""
        var event = new MouseEvent('mousemove', {
            'view': window,
            'bubbles': true,
            'cancelable': true,
            'clientX': Math.floor(Math.random() * window.innerWidth),
            'clientY': Math.floor(Math.random() * window.innerHeight)
        });
        document.dispatchEvent(event);
    """)

    # Получаем и выводим текст страницы
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print(body_text)

    # Оставляем браузер открытым для проверки
    input("Нажмите Enter для закрытия браузера...")

except Exception as e:
    print(f"Произошла ошибка: {e}")

finally:
    # Закрываем браузер
    driver.quit()
