import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

import undetected_chromedriver as uc
from selenium.webdriver import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By


class UndetectedSetup:
    def __init__(self, profile_name="default"):
        self.profile_path, self.user_agent = self.create_or_get_profile(profile_name)
        self.options = self.setup_options()
        self.driver = None

    def get_random_user_agent(self):
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
        ]
        return random.choice(user_agents)

    def create_or_get_profile(self, profile_name):
        profiles_dir = os.path.join(os.getcwd(), "chrome_profiles")
        profile_path = os.path.join(profiles_dir, profile_name)

        if not os.path.exists(profile_path):
            os.makedirs(profile_path)

        metadata_path = os.path.join(profile_path, "metadata.json")
        if not os.path.exists(metadata_path):
            metadata = {
                "created_at": time.time(),
                "last_used": time.time(),
                "user_agent": self.get_random_user_agent()
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

    def setup_options(self):
        options = uc.ChromeOptions()
        options.add_argument(f'user-agent={self.user_agent}')
        options.add_argument("--window-size=1366,768")
        options.add_argument("--enable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--user-data-dir={self.profile_path}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--lang=de-DE")
        options.add_argument("--timezone=Europe/Berlin")
        options.add_argument('--use-fake-ui-for-media-stream')
        options.add_argument('--use-fake-device-for-media-stream')
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-save-password-bubble")
        options.add_argument("--ignore-certificate-errors")
        return options

    def initialize_driver(self):
        self.driver = uc.Chrome(options=self.options)
        self.driver.set_window_size(1366, 768)
        self.mask_webdriver()
        self.randomize_webgl()
        self.set_german_time()

    def mask_webdriver(self):
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def randomize_webgl(self):
        self.driver.execute_script("""
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

    def set_german_time(self):
        german_time = datetime.now(timezone.utc) + timedelta(hours=1)
        self.driver.execute_script(
            f"Date.prototype.getTimezoneOffset = function() {{ return -60; }}; Date.now = function() {{ return new Date({german_time.timestamp() * 1000}).getTime(); }};")

    def random_sleep(self, min_milliseconds=1000, max_milliseconds=5000):
        time.sleep(random.randint(min_milliseconds, max_milliseconds) / 1000)

    def human_like_mouse_move(self, start_x, start_y, end_x, end_y):
        steps = random.randint(50, 100)
        for i in range(steps):
            t = i / steps
            x = int(start_x + (end_x - start_x) * (t + random.uniform(-0.1, 0.1)))
            y = int(start_y + (end_y - start_y) * (t + random.uniform(-0.1, 0.1)))
            try:
                self.driver.execute_script(f"""
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
            self.random_sleep(10, 20)  # 10-20 миллисекунд

    def random_click(self):
        clickable_elements = self.driver.find_elements(By.CSS_SELECTOR, 'a, button, input[type="submit"]')
        if clickable_elements:
            element = random.choice(clickable_elements)
            self.human_like_mouse_move(
                random.randint(0, self.driver.execute_script("return window.innerWidth;")),
                random.randint(0, self.driver.execute_script("return window.innerHeight;")),
                element.location['x'],
                element.location['y']
            )
            element.click()
            self.random_sleep(1000, 3000)

    def simulate_keyboard_input(self):
        element = self.driver.find_element(By.TAG_NAME, 'body')
        random_text = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(5, 10)))
        for char in random_text:
            element.send_keys(char)
            self.random_sleep(100, 300)  # 100-300 миллисекунд
        self.random_sleep(500, 1500)  # 500-1500 миллисекунд
        for _ in range(len(random_text)):
            element.send_keys(Keys.BACKSPACE)
            self.random_sleep(100, 300)  # 100-300 миллисекунд

    def random_pause(self):
        if random.random() < 0.1:  # 10% шанс на длительную паузу
            self.random_sleep(5000, 15000)  # 5-15 секунд
        else:
            self.random_sleep(500, 2000)  # 0.5-2 секунды

    def add_random_headers(self):
        headers = {
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        self.driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': headers})

    def simulate_human_behavior(self):
        try:
            window_width = self.driver.execute_script("return window.innerWidth;")
            window_height = self.driver.execute_script("return window.innerHeight;")

            self.random_pause()

            # Случайное движение мыши
            num_movements = random.randint(1, 5)
            for _ in range(num_movements):
                start_x, start_y = random.randint(0, window_width), random.randint(0, window_height)
                end_x, end_y = random.randint(0, window_width), random.randint(0, window_height)
                self.human_like_mouse_move(start_x, start_y, end_x, end_y)
                self.random_pause()

            # Случайный клик
            if random.random() < 0.3:  # 30% шанс на клик
                try:
                    self.random_click()
                except Exception as e:
                    print(f"Ошибка при клике: {e}")
                self.random_pause()

            # Случайный ввод с клавиатуры
            if random.random() < 0.2:  # 20% шанс на ввод с клавиатуры
                try:
                    self.simulate_keyboard_input()
                except Exception as e:
                    print(f"Ошибка при вводе с клавиатуры: {e}")
                self.random_pause()

            # Случайный скролл
            scroll_y = random.randint(100, min(1000, window_height))
            self.driver.execute_script(f"window.scrollTo(0, {scroll_y});")
            self.random_pause()

        except Exception as e:
            print(f"Ошибка при симуляции поведения: {e}")

    def get_driver(self):
        return self.driver
