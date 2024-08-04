import asyncio
import json
import logging
import time
import traceback

from undetected import UndetectedSetup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_recorded_events():
    try:
        with open("recorded_events.json", "r") as f:
            events = json.load(f)
        return [normalize_event(event) for event in events]
    except FileNotFoundError:
        logger.error("recorded_events.json not found")
        return []
    except json.JSONDecodeError:
        logger.error("Error decoding recorded_events.json")
        return []


def normalize_event(event):
    required_fields = ['type', 'time', 'url']
    for field in required_fields:
        if field not in event:
            if field == 'time':
                event[field] = int(time.time() * 1000)
            else:
                event[field] = ''
    return event


async def perform_click(tab, click_event, max_retries=3, retry_delay=1):
    try:
        text = click_event.get('elementDescription') or click_event.get('text_all') or click_event.get(
            'textContent') or click_event.get('innerText')
        shadow_path = click_event['shadowPath']
        custom_selector = click_event['customSelector']

        for attempt in range(max_retries):
            element = None
            try:
                if text:
                    element = await tab.find(text, best_match=True, timeout=10)
                if not element and shadow_path:
                    js_code = f"""
                    (function() {{
                        function getElementByShadowPath(path) {{
                            const parts = path.split(' > ');
                            let element = window;
                            for (const part of parts) {{
                                if (part === 'document') {{
                                    element = element.document;
                                }} else if (part === 'shadowRoot') {{
                                    if (element.shadowRoot) {{
                                        element = element.shadowRoot;
                                    }} else {{
                                        console.error('No shadow root found for element:', element);
                                        return null;
                                    }}
                                }} else {{
                                    const [tag, ...classes] = part.split('.');
                                    if (typeof element.querySelector === 'function') {{
                                        element = element.querySelector(tag + (classes.length ? '.' + classes.join('.') : ''));
                                    }} else {{
                                        console.error('querySelector is not a function for element:', element);
                                        return null;
                                    }}
                                    if (!element) return null;
                                }}
                            }}
                            return element;
                        }}
                        return getElementByShadowPath("{shadow_path}");
                    }})();
                    """
                    element = await tab.evaluate(js_code)
                if not element and custom_selector:
                    element = await tab.query_selector(custom_selector)

                if element:
                    await element.click()
                    logger.info(f"Clicked element: {click_event['tagName']} - {text or shadow_path or custom_selector}")
                    return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                await asyncio.sleep(retry_delay)

        logger.warning(f"Element not found after {max_retries} attempts: {text or shadow_path or custom_selector}")
    except Exception as e:
        logger.error(f"Error performing click: {e}")
        logger.error(traceback.format_exc())


async def perform_input(tab, input_event, browser, max_retries=3, retry_delay=1):
    try:
        custom_selector = input_event['customSelector']
        value = input_event['value']
        shadow_path = input_event['shadowPath']
        target_url = input_event['url']

        extension_tab = None
        for existing_tab in browser.tabs:
            tab_url = await existing_tab.evaluate("window.location.href")
            if tab_url.startswith(target_url):
                extension_tab = existing_tab
                break

        if extension_tab:
            await extension_tab.activate()
            logger.info(f"Switched to existing extension tab: {target_url}")
            await asyncio.sleep(2)
        else:
            logger.warning(f"Extension tab not found: {target_url}")
            return

        for attempt in range(max_retries):
            try:
                js_code = f"""
                (function() {{
                    function getElementByPath(path) {{
                        const parts = path.split(' > ').reverse();
                        let element = document;
                        for (const part of parts) {{
                            if (part === 'shadowRoot') {{
                                element = element.shadowRoot;
                            }} else if (part.startsWith('html')) {{
                                element = document.documentElement;
                            }} else if (part.startsWith('body')) {{
                                element = document.body;
                            }} else {{
                                const [tag, ...classes] = part.split('.');
                                element = element.querySelector(tag + (classes.length ? '.' + classes.join('.') : ''));
                            }}
                            if (!element) return null;
                        }}
                        return element;
                    }}

                    const element = getElementByPath("{shadow_path}") || document.querySelector("{custom_selector}");
                    if (element) {{
                        const originalDesc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
                        Object.defineProperty(element, 'value', {{
                            get: function() {{ return originalDesc.get.call(this); }},
                            set: function(val) {{
                                originalDesc.set.call(this, val);
                                this.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                this.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }});
                        element.value = "{value}";
                        return true;
                    }}
                    return false;
                }})();
                """

                success = await extension_tab.evaluate(js_code)

                if success:
                    logger.info(f"Set value: {value} for element: {custom_selector}")
                    await asyncio.sleep(1)
                    return
                else:
                    raise Exception("Failed to find or set value for element")
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                await asyncio.sleep(retry_delay)

        logger.warning(f"Failed to set value after {max_retries} attempts: {custom_selector}")
    except Exception as e:
        logger.error(f"Error performing input: {e}")
        logger.error(traceback.format_exc())


async def replay_events(setup):
    browser = setup.browser
    recorded_events = load_recorded_events()

    logger.info(f"Loaded {len(recorded_events)} events for replay")

    if not recorded_events:
        logger.warning("No recorded events found")
        return

    main_tab = browser.main_tab
    logger.info("Navigating to the initial URL")
    await main_tab.get("https://miles.plumenetwork.xyz/")
    logger.info("Page loaded. Waiting for 5 seconds before starting to replay events.")
    await asyncio.sleep(5)
    logger.info("Starting to replay events.")

    current_tab = main_tab
    extension_tabs = {}
    previous_url = None

    for index, event in enumerate(recorded_events):
        try:
            logger.info(f"Processing event {index + 1}/{len(recorded_events)}: {event['type']}")
            url = event.get('url')

            # Проверяем, изменился ли URL
            if url and url != previous_url:
                logger.info(f"URL changed. Searching for tab with URL: {url}")
                found_tab = None
                for tab in browser.tabs:
                    tab_url = await tab.evaluate("window.location.href")
                    if tab_url.startswith(url):
                        found_tab = tab
                        break

                if found_tab:
                    current_tab = found_tab
                    await current_tab.activate()
                    logger.info(f"Switched to tab with URL: {url}")
                else:
                    logger.warning(f"Tab with URL {url} not found. Staying on current tab.")

                previous_url = url

            if event['type'] == 'click':
                logger.info("Performing click action")
                await perform_click(current_tab, event)
            elif event['type'] == 'input':
                logger.info("Performing input action")
                await perform_input(current_tab, event, browser)  # Передаем browser
            else:
                logger.warning(f"Unknown event type: {event['type']}")

            logger.info(f"Finished processing event {index + 1}")
            await asyncio.sleep(2)  # Увеличиваем задержку между событиями

        except Exception as e:
            logger.error(f"Error processing event {index + 1}: {str(e)}")
            logger.error(traceback.format_exc())

    logger.info("Finished replaying all events")


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
        await replay_events(setup)
    except Exception as e:
        logger.error(f"An error occurred in main: {e}")
        logger.error(traceback.format_exc())
    finally:
        if setup.browser:
            try:
                await setup.close_browser()
            except Exception as close_error:
                logger.error(f"Error closing browser: {close_error}")


if __name__ == "__main__":
    asyncio.run(main())
