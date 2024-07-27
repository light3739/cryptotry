import asyncio
import json
import logging
import traceback

from undetected import UndetectedSetup

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ClickRecorder:
    def __init__(self):
        self.clicks = []

async def inject_click_listener(tab):
    js_code = """
    if (typeof window.clickEvents === 'undefined') {
        window.clickEvents = [];
    }

    function getXPath(element) {
        if (element.id !== '')
            return 'id("' + element.id + '")';
        if (element === document.body)
            return element.tagName;

        var ix = 0;
        var siblings = element.parentNode.childNodes;
        for (var i = 0; i < siblings.length; i++) {
            var sibling = siblings[i];
            if (sibling === element)
                return getXPath(element.parentNode) + '/' + element.tagName + '[' + (ix + 1) + ']';
            if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                ix++;
        }
    }

    document.addEventListener('click', function(e) {
        var element = e.target;
        var eventData = {
            type: 'click',
            tagName: element.tagName,
            id: element.id,
            className: element.className,
            xpath: getXPath(element),
            textContent: element.textContent,
            innerText: element.innerText,
            time: new Date().getTime()
        };
        window.clickEvents.push(eventData);
        console.log('Click event:', JSON.stringify(eventData));
    }, true);
    """
    await tab.evaluate(js_code)

async def get_click_events(tab):
    events = await tab.evaluate("window.clickEvents")
    if events:
        await tab.evaluate("window.clickEvents = []")
    return events

async def record_clicks(setup, recorder, stop_event):
    main_tab = setup.browser.main_tab

    await main_tab.get("https://miles.plumenetwork.xyz/")
    await inject_click_listener(main_tab)

    print("Recording started. Perform your actions.")
    print("Press 'q' and Enter to stop recording.")

    while not stop_event.is_set():
        click_events = await get_click_events(main_tab)
        if click_events:
            recorder.clicks.extend(click_events)
        await asyncio.sleep(0.1)

async def input_listener(stop_event):
    while True:
        user_input = await asyncio.get_event_loop().run_in_executor(None, input)
        if user_input.lower() == 'q':
            stop_event.set()
            break

async def main():
    proxy = {
        'host': '45.13.195.53',
        'port': '30001',
        'user': 'vintarik8_gmail_com',
        'pass': 'c560667e15'
    }
    setup = UndetectedSetup("my_profile", proxy=proxy)
    recorder = ClickRecorder()
    stop_event = asyncio.Event()

    try:
        await setup.initialize_driver()

        record_task = asyncio.create_task(record_clicks(setup, recorder, stop_event))
        input_task = asyncio.create_task(input_listener(stop_event))

        await asyncio.gather(record_task, input_task)

    except Exception as e:
        logger.error(f"An error occurred in main: {e}")
        logger.error(traceback.format_exc())
    finally:
        if setup.browser:
            await setup.close_browser()

        with open("recorded_clicks.json", "w") as f:
            json.dump(recorder.clicks, f, indent=2)
        print("Clicks recorded and saved to recorded_clicks.json")

if __name__ == "__main__":
    asyncio.run(main())
