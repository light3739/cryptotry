import time
import json
from pynput import mouse, keyboard
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class ActionRecorder:
    def __init__(self):
        self.actions = []
        self.recording = False
        self.mouse_listener = mouse.Listener(on_click=self.on_click, on_move=self.on_move)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        self.driver.get("https://miles.plumenetwork.xyz/")  # Замените на нужный URL
        self.driver.maximize_window()

    def start_recording(self):
        self.recording = True
        self.mouse_listener.start()
        self.keyboard_listener.start()
        print("Recording started. Press 'q' to stop recording.")

    def stop_recording(self):
        self.recording = False
        self.mouse_listener.stop()
        self.keyboard_listener.stop()
        self.driver.quit()
        print("Recording stopped.")

    def on_click(self, x, y, button, pressed):
        if self.recording and pressed:
            element = self.get_element_at_position(x, y)
            self.actions.append({
                "type": "click",
                "x": x,
                "y": y,
                "selector": self.get_css_selector(element) if element else None,
                "time": time.time()
            })

    def on_move(self, x, y):
        if self.recording:
            self.actions.append({"type": "move", "x": x, "y": y, "time": time.time()})

    def on_press(self, key):
        if key == keyboard.KeyCode.from_char('q'):
            self.stop_recording()
            return False

    def get_element_at_position(self, x, y):
        return self.driver.execute_script(
            f"return document.elementFromPoint({x}, {y});"
        )

    def get_css_selector(self, element):
        return self.driver.execute_script(
            "function getPathTo(element) {"
            "    if (element.id !== '')"
            "        return 'id(\"' + element.id + '\")';"
            "    if (element === document.body)"
            "        return element.tagName;"
            "    var ix = 0;"
            "    var siblings = element.parentNode.childNodes;"
            "    for (var i = 0; i < siblings.length; i++) {"
            "        var sibling = siblings[i];"
            "        if (sibling === element)"
            "            return getPathTo(element.parentNode) + '/' + element.tagName + '[' + (ix + 1) + ']';"
            "        if (sibling.nodeType === 1 && sibling.tagName === element.tagName)"
            "            ix++;"
            "    }"
            "}"
            "return getPathTo(arguments[0]);",
            element
        )

    def save_actions(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.actions, f)
        print(f"Actions saved to {filename}")


def record_actions():
    recorder = ActionRecorder()
    recorder.start_recording()
    recorder.keyboard_listener.join()
    recorder.save_actions("recorded_actions.json")


def replay_actions(filename):
    with open(filename, 'r') as f:
        actions = json.load(f)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get("https://miles.plumenetwork.xyz/")  # Замените на нужный URL
    driver.maximize_window()

    action_chains = ActionChains(driver)
    wait = WebDriverWait(driver, 10)

    for action in actions:
        if action["type"] == "move":
            action_chains.move_by_offset(action["x"], action["y"])
        elif action["type"] == "click":
            if action["selector"]:
                try:
                    element = wait.until(EC.element_to_be_clickable((By.XPATH, action["selector"])))
                    action_chains.move_to_element(element).click()
                except:
                    action_chains.move_by_offset(action["x"], action["y"]).click()
            else:
                action_chains.move_by_offset(action["x"], action["y"]).click()

        action_chains.pause(0.1)

    action_chains.perform()

    input("Press Enter to close the browser...")
    driver.quit()


if __name__ == "__main__":
    choice = input("Enter 'r' to record or 'p' to play: ")
    if choice.lower() == 'r':
        record_actions()
    elif choice.lower() == 'p':
        replay_actions("recorded_actions.json")
    else:
        print("Invalid choice")
