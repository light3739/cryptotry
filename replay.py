import asyncio
import json
import logging
import traceback

from undetected import UndetectedSetup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_recorded_clicks():
    try:
        with open("recorded_clicks.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("recorded_clicks.json not found")
        return []
    except json.JSONDecodeError:
        logger.error("Error decoding recorded_clicks.json")
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


async def replay_clicks(setup):
    browser = setup.browser
    recorded_clicks = load_recorded_clicks()

    if not recorded_clicks:
        logger.warning("No recorded clicks found")
        return

    main_tab = browser.main_tab
    await main_tab.get("https://miles.plumenetwork.xyz/")
    logger.info("Page loaded. Waiting for 5 seconds before starting to replay clicks.")
    await asyncio.sleep(5)
    logger.info("Starting to replay clicks.")

    current_tab = main_tab

    for click_event in recorded_clicks:
        url = click_event.get('url')
        if url and not url.startswith("chrome-extension://"):
            # Only switch tabs for non-extension URLs
            if url != await current_tab.evaluate("window.location.href"):
                # Try to find an existing tab with the same URL
                found_tab = None
                for tab in browser.tabs:
                    if await tab.evaluate("window.location.href") == url:
                        found_tab = tab
                        break

                if not found_tab:
                    # If no existing tab is found, create a new one
                    new_tab = await browser.new_tab()
                    await new_tab.get(url)
                    current_tab = new_tab
                else:
                    current_tab = found_tab

                await current_tab.activate()
                # Wait for the page to load
                await current_tab.wait_for('load')

        await perform_click(current_tab, click_event)
        await asyncio.sleep(2)  # Увеличиваем задержку между кликами

    logger.info("Finished replaying clicks")


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
        await replay_clicks(setup)
    except Exception as e:
        logger.error(f"An error occurred in main: {e}")
        logger.error(traceback.format_exc())
    finally:
        if setup.browser:
            await setup.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
