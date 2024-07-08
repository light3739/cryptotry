from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException, NoSuchWindowException, StaleElementReferenceException, TimeoutException
import time

def initialize_driver():
    extension_path = (r'C:\Users\maxik\AppData\Local\Google\Chrome\User '
                      r'Data\Default\Extensions\acmacodkjbdgmoleebolmdjonilkdbch\0.92.78_0')

    options = Options()
    options.add_argument(f'--load-extension={extension_path}')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option("detach", True)

    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    print("WebDriver успешно инициализирован")
    return driver

def wait_and_click(driver, xpath, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        element.click()
        print(f"Кликнул по элементу: {xpath}")
        return True
    except TimeoutException:
        print(f"Элемент не найден или не кликабелен: {xpath}")
        return False
    except Exception as e:
        print(f"Ошибка при клике на элемент {xpath}: {e}")
        return False

def monitor_and_interact(driver):
    while True:
        try:
            current_url = driver.current_url
            print(f"\nТекущий URL: {current_url}")

            if "welcome" in current_url:
                if wait_and_click(driver, "//button[contains(text(), 'Next')]"):
                    continue

            if "no-address" in current_url:
                if wait_and_click(driver, "//div[contains(text(), 'Create New Seed Phrase')]"):
                    continue

            # Добавьте здесь дополнительные действия для других страниц

            print("\nДоступные элементы на странице:")
            elements = driver.find_elements(By.XPATH, "//*[self::a or self::button or self::input]")
            for elem in elements:
                try:
                    print(f"Тег: {elem.tag_name}, Текст: {elem.text}, ID: {elem.get_attribute('id')}, "
                          f"Class: {elem.get_attribute('class')}, Href: {elem.get_attribute('href')}")
                except StaleElementReferenceException:
                    print("Элемент устарел")
                except Exception as e:
                    print(f"Ошибка при получении информации об элементе: {e}")

        except NoSuchWindowException:
            print("Окно браузера было закрыто. Попытка переключиться на другое окно...")
            try:
                driver.switch_to.window(driver.window_handles[-1])
            except:
                print("Все окна закрыты. Завершение работы.")
                return

        except WebDriverException as e:
            print(f"Произошла ошибка WebDriver: {e}")

        except Exception as e:
            print(f"Неизвестная ошибка: {e}")

        time.sleep(2)

def main():
    driver = initialize_driver()
    if not driver:
        print("Не удалось инициализировать драйвер. Программа завершена.")
        return

    try:
        time.sleep(5)
        print("Открытые вкладки:")
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            print(f"- {driver.current_url}")

        driver.switch_to.window(driver.window_handles[-1])

        print("\nНачинаем мониторинг и взаимодействие. Нажмите Ctrl+C для завершения.")
        monitor_and_interact(driver)

    except KeyboardInterrupt:
        print("\nПрограмма завершена пользователем.")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
    finally:
        try:
            driver.quit()
        except:
            print("Браузер уже был закрыт.")

if __name__ == "__main__":
    main()
