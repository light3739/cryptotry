import asyncio
import json
import logging
import traceback

from undetected import UndetectedSetup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_recorded_events():
    try:
        with open("recorded_events.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("recorded_events.json not found")
        return []
    except json.JSONDecodeError:
        logger.error("Error decoding recorded_events.json")
        return []


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


async def perform_input(tab, input_event, max_retries=3, retry_delay=1):
    try:
        custom_selector = input_event['customSelector']
        value = input_event['value']
        tag_name = input_event['tagName']
        class_name = input_event['className']

        for attempt in range(max_retries):
            try:
                # Попробуем найти элемент несколькими способами
                element = None

                # Используем JavaScript для поиска элемента, что позволит работать в контексте расширения
                js_code = f"""
                (function() {{
                    let element = null;
                    // 1. Попробуем найти любой input на странице
                    if (!element) {{
                        element = document.querySelector('input');
                        if (element) console.log("Found element using general input selector");
                    }}
                    // 2. Попробуем найти по атрибуту type="text" или type="password"
                    if (!element) {{
                        element = document.querySelector('{tag_name.lower()}[type="text"], {tag_name.lower()}[type="password"]');
                        if (element) console.log("Found element using type attribute");
                    }}
                    // 3. Попробуем найти по тегу и классу
                    if (!element) {{
                        element = document.querySelector('{tag_name.lower()}[class*="{class_name}"]');
                        if (element) console.log("Found element using tag and class");
                    }}
                    // 4. Попробуем найти по custom_selector
                    if (!element) {{
                        element = document.querySelector('{custom_selector}');
                        if (element) console.log("Found element using custom selector");
                    }}
                    return element;
                }})();
                """
                element = await tab.evaluate(js_code)

                if element:
                    # Используем JavaScript для очистки и ввода текста
                    await tab.evaluate(f"""
                    (function() {{
                        let element = document.querySelector('{custom_selector}');
                        if (element) {{
                            element.value = '';
                            element.value = '{value}';
                            element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }})();
                    """)
                    logger.info(f"Entered text: {value} into element: {custom_selector}")
                    return
                else:
                    raise Exception("Element not found")
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                await asyncio.sleep(retry_delay)

        logger.warning(f"Element not found after {max_retries} attempts: {custom_selector}")
    except Exception as e:
        logger.error(f"Error performing input: {e}")
        logger.error(traceback.format_exc())


async def replay_events(setup):
    browser = setup.browser
    recorded_events = load_recorded_events()

    if not recorded_events:
        logger.warning("No recorded events found")
        return

    main_tab = browser.main_tab
    await main_tab.get("https://miles.plumenetwork.xyz/")
    logger.info("Page loaded. Waiting for 5 seconds before starting to replay events.")
    await asyncio.sleep(5)
    logger.info("Starting to replay events.")

    current_tab = main_tab
    extension_tabs = {}

    for event in recorded_events:
        url = event.get('url')
        if url:
            if url.startswith("chrome-extension://"):
                # Для URL-адресов расширений Chrome ищем существующую вкладку или создаем новую
                if url not in extension_tabs:
                    found_tab = None
                    for tab in browser.tabs:
                        tab_url = await tab.evaluate("window.location.href")
                        if tab_url.startswith(url):
                            found_tab = tab
                            break

                    if not found_tab:
                        logger.info(f"Creating new tab for Chrome extension URL: {url}")
                        new_tab = await browser.new_tab()
                        await new_tab.get(url)
                        extension_tabs[url] = new_tab
                    else:
                        logger.info(f"Found existing tab for Chrome extension URL: {url}")
                        extension_tabs[url] = found_tab

                current_tab = extension_tabs[url]
                await current_tab.activate()
                await current_tab.wait_for('load')
            elif url != await current_tab.evaluate("window.location.href"):
                found_tab = None
                for tab in browser.tabs:
                    if await tab.evaluate("window.location.href") == url:
                        found_tab = tab
                        break

                if not found_tab:
                    new_tab = await browser.new_tab()
                    await new_tab.get(url)
                    current_tab = new_tab
                else:
                    current_tab = found_tab

                await current_tab.activate()
                await current_tab.wait_for('load')

        logger.info(f"Current URL: {await current_tab.evaluate('window.location.href')}")

        if event['type'] == 'click':
            await perform_click(current_tab, event)
        elif event['type'] == 'input':
            await perform_input(current_tab, event)
        else:
            logger.warning(f"Unknown event type: {event['type']}")

        await asyncio.sleep(2)  # Увеличиваем задержку между событиями

    logger.info("Finished replaying events")


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

if __name__ == "__main__":
    asyncio.run(main())
