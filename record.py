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

    function getComposedPath(element) {
        let path = [];
        while (element) {
            path.push(element);
            if (element.tagName === 'HTML') {
                path.push(document);
                path.push(window);
                return path;
            }
            element = element.parentNode || element.host;
        }
        return path;
    }

    function getShadowRootPath(element) {
        const path = getComposedPath(element);
        return path.map(el => {
            if (el === window) return 'window';
            if (el === document) return 'document';
            if (el instanceof ShadowRoot) return 'shadowRoot';
            return el.tagName.toLowerCase() + (el.id ? `#${el.id}` : '') + (el.className ? `.${el.className.replace(/\\s+/g, '.')}` : '');
        }).join(' > ');
    }

    function getCustomSelector(element) {
        if (element.id) return '#' + element.id;
        if (element.className) {
            const classes = element.className.split(/\\s+/).filter(Boolean);
            if (classes.length) return '.' + classes.join('.');
        }
        return element.tagName.toLowerCase();
    }

    function getAllText(element) {
        return element.innerText || element.textContent || '';
    }

    function getButtonDescription(element) {
        if (element.tagName.toLowerCase() === 'button') {
            const text = getAllText(element).trim();
            if (!text) {
                // Если у кнопки нет текста, попробуем найти иконку или другое содержимое
                const iconElement = element.querySelector('i, svg, img');
                if (iconElement) {
                    return `Button with ${iconElement.tagName.toLowerCase()}`;
                }
                return 'Button without text';
            }
            return text;
        }
        return null;
    }

    document.addEventListener('click', function(e) {
        var element = e.composedPath()[0];
        var eventData = {
            type: 'click',
            tagName: element.tagName,
            id: element.id,
            className: element.className,
            shadowPath: getShadowRootPath(element),
            customSelector: getCustomSelector(element),
            textContent: element.textContent.trim(),
            innerText: element.innerText.trim(),
            text_all: getAllText(element).trim(),
            buttonDescription: getButtonDescription(element),
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
