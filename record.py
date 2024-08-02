import asyncio
import json
import logging
import traceback

from undetected import UndetectedSetup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EventRecorder:
    def __init__(self):
        self.events = []
        self.tabs = []
        self.last_input = {}  # Хранит последнее событие ввода для каждого элемента


async def inject_event_listener(tab):
    js_code = """
    if (typeof window.recordedEvents === 'undefined') {
        window.recordedEvents = [];
    }
    if (typeof window.lastInputEvent === 'undefined') {
        window.lastInputEvent = {};
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
        if (element.tagName.toLowerCase() === 'slot') {
            return Array.from(element.assignedNodes())
                .map(node => node.textContent || '')
                .join(' ')
                .trim();
        }
        return element.innerText || element.textContent || '';
    }

    function getElementDescription(element) {
        function getElementText(el) {
            const text = getAllText(el).trim();
            if (text) return text;

            for (const child of el.children) {
                const childText = getElementText(child);
                if (childText) return childText;
            }

            if (el.shadowRoot) {
                const shadowText = getElementText(el.shadowRoot);
                if (shadowText) return shadowText;
            }

            return '';
        }

        const elementText = getElementText(element);

        if (elementText) {
            return elementText;
        } else {
            const iconElement = element.querySelector('i, svg, img');
            if (iconElement) {
                return `Element with ${iconElement.tagName.toLowerCase()}`;
            }
            return 'Element without text';
        }
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
            elementDescription: getElementDescription(element),
            time: new Date().getTime()
        };
        
        // Добавляем последнее событие ввода перед кликом, если оно есть
        if (window.lastInputEvent[eventData.customSelector]) {
            window.recordedEvents.push(window.lastInputEvent[eventData.customSelector]);
            delete window.lastInputEvent[eventData.customSelector];
        }
        
        window.recordedEvents.push(eventData);
        console.log('Click event:', JSON.stringify(eventData));
    }, true);

    document.addEventListener('input', function(e) {
        var element = e.target;
        var eventData = {
            type: 'input',
            tagName: element.tagName,
            id: element.id,
            className: element.className,
            shadowPath: getShadowRootPath(element),
            customSelector: getCustomSelector(element),
            value: element.value,
            time: new Date().getTime()
        };
        window.lastInputEvent[eventData.customSelector] = eventData;
        console.log('Input event:', JSON.stringify(eventData));
    }, true);
    """
    await tab.evaluate(js_code)


async def get_recorded_events(tab):
    events = await tab.evaluate("window.recordedEvents")
    last_input = await tab.evaluate("window.lastInputEvent")
    if events:
        await tab.evaluate("window.recordedEvents = []")
    if last_input:
        await tab.evaluate("window.lastInputEvent = {}")
    return events, last_input


async def record_events(setup, recorder, stop_event):
    browser = setup.browser
    main_tab = browser.main_tab

    try:
        await main_tab.get("https://miles.plumenetwork.xyz/")
        await inject_event_listener(main_tab)
        recorder.tabs.append(main_tab)

        print("Recording started. Perform your actions.")
        print("Press 'q' and Enter to stop recording.")

        while not stop_event.is_set():
            try:
                current_tabs = browser.tabs
                new_tabs = [tab for tab in current_tabs if tab not in recorder.tabs]
                for tab in new_tabs:
                    try:
                        await inject_event_listener(tab)
                        recorder.tabs.append(tab)
                    except Exception as inject_error:
                        logger.error(f"Error injecting event listener: {inject_error}")

                for tab in recorder.tabs:
                    try:
                        events, last_input = await get_recorded_events(tab)
                        if events or last_input:
                            try:
                                current_url = await tab.evaluate("window.location.href")
                                if events:
                                    for event in events:
                                        event['url'] = current_url
                                    recorder.events.extend(events)

                                if last_input:
                                    for selector, event in last_input.items():
                                        event['url'] = current_url
                                        recorder.last_input[selector] = event
                            except Exception as url_error:
                                logger.error(f"Error getting URL: {url_error}")
                    except Exception as tab_error:
                        if "server rejected WebSocket connection: HTTP 500" in str(tab_error):
                            logger.warning(f"WebSocket connection rejected. Retrying in 5 seconds...")
                            await asyncio.sleep(5)
                            continue
                        logger.error(f"Error processing tab: {tab_error}")

                recorder.tabs = [tab for tab in recorder.tabs if tab in current_tabs]

            except Exception as loop_error:
                logger.error(f"Error in main loop: {loop_error}")

            await asyncio.sleep(0.1)

    except Exception as e:
        logger.error(f"Error in record_events: {e}")
        logger.error(traceback.format_exc())


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
    recorder = EventRecorder()
    stop_event = asyncio.Event()

    try:
        await setup.initialize_driver()

        record_task = asyncio.create_task(record_events(setup, recorder, stop_event))
        input_task = asyncio.create_task(input_listener(stop_event))

        await asyncio.gather(record_task, input_task)

    except Exception as e:
        logger.error(f"An error occurred in main: {e}")
        logger.error(traceback.format_exc())
    finally:
        if setup.browser:
            await setup.close_browser()

        # Добавляем оставшиеся события ввода в конец списка событий
        for input_event in recorder.last_input.values():
            recorder.events.append(input_event)

        with open("recorded_events.json", "w") as f:
            json.dump(recorder.events, f, indent=2)
        print("Events recorded and saved to recorded_events.json")


if __name__ == "__main__":
    asyncio.run(main())
