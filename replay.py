import asyncio
import json
import logging
import time
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


async def perform_click(tab, click_event):
    try:
        text = click_event.get('text_all') or click_event.get('textContent') or click_event.get('innerText')
        shadow_path = click_event['shadowPath']
        custom_selector = click_event['customSelector']

        element = None
        if text:
            element = await tab.find(text, best_match=True)
        if not element and shadow_path:
            js_code = f"""
            function getElementByShadowPath(path) {{
                const parts = path.split(' > ');
                let element = window;
                for (const part of parts) {{
                    if (part === 'document') {{
                        element = element.document;
                    }} else if (part === 'shadowRoot') {{
                        element = element.shadowRoot;
                    }} else {{
                        const [tag, ...classes] = part.split('.');
                        element = element.querySelector(tag + (classes.length ? '.' + classes.join('.') : ''));
                        if (!element) return null;
                    }}
                }}
                return element;
            }}
            return getElementByShadowPath("{shadow_path}");
            """
            element = await tab.evaluate(js_code)
        if not element and custom_selector:
            element = await tab.query_selector(custom_selector)

        if element:
            await element.click()
            logger.info(f"Clicked element: {click_event['tagName']} - {text or shadow_path or custom_selector}")
        else:
            logger.warning(f"Element not found: {text or shadow_path or custom_selector}")
    except Exception as e:
        logger.error(f"Error performing click: {e}")


async def replay_clicks(setup):
    main_tab = setup.browser.main_tab
    recorded_clicks = load_recorded_clicks()

    if not recorded_clicks:
        logger.warning("No recorded clicks found")
        return

    await main_tab.get("https://miles.plumenetwork.xyz/")
    logger.info("Page loaded. Waiting for 5 seconds before starting to replay clicks.")
    await asyncio.sleep(5)
    logger.info("Starting to replay clicks.")

    for click_event in recorded_clicks:
        await perform_click(main_tab, click_event)
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
    time.sleep(5)
