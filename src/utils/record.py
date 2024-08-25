import asyncio
import json
import logging
import traceback
from collections import deque
from dataclasses import asdict, dataclass
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Event:
    type: str
    url: str
    timestamp: float
    details: Dict[str, Any]


class EventBuffer:
    def __init__(self, max_size: int = 1000):
        self.buffer = deque(maxlen=max_size)

    def add_event(self, event: Event):
        self.buffer.append(event)

    def get_events(self) -> List[Event]:
        events = list(self.buffer)
        self.buffer.clear()
        return events


class TabManager:
    def __init__(self):
        self.tabs = {}
        self.extension_tabs = {}

    async def add_tab(self, tab):
        url = await tab.evaluate("window.location.href")
        if url.startswith("chrome-extension://"):
            self.extension_tabs[url] = tab
        else:
            self.tabs[url] = tab
        await inject_event_listener(tab)

    async def remove_inactive_tabs(self, current_tabs):
        self.tabs = {url: tab for url, tab in self.tabs.items() if tab in current_tabs}
        self.extension_tabs = {url: tab for url, tab in self.extension_tabs.items() if tab in current_tabs}

    def get_all_tabs(self):
        return list(self.tabs.values()) + list(self.extension_tabs.values())


class EventRecorder:
    def __init__(self, configuration):
        self.event_buffer = EventBuffer()
        self.tab_manager = TabManager()
        self.configuration = configuration

    async def process_tab(self, tab):
        try:
            current_url = await tab.evaluate("window.location.href")
            events, last_input = await get_recorded_events(tab)

            for event_data in events:
                event = Event(
                    type=event_data['type'],
                    url=current_url,
                    timestamp=event_data['time'],
                    details=event_data
                )
                self.event_buffer.add_event(event)
                self.save_event(event)  # Сохраняем событие сразу

            if last_input:
                for selector, input_event in last_input.items():
                    event = Event(
                        type='input',
                        url=current_url,
                        timestamp=input_event['time'],
                        details=input_event
                    )
                    self.event_buffer.add_event(event)
                    self.save_event(event)  # Сохраняем событие сразу

            logger.info(f"Processed {len(events)} events for tab: {current_url}")
        except Exception as tab_error:
            logger.error(f"Error processing tab: {tab_error}")

    def save_event(self, event):
        formatted_event = self.format_event(event)
        if 'events' not in self.configuration.data:
            self.configuration.data['events'] = []
        self.configuration.data['events'].append(formatted_event)
        self.save_configuration()

    def format_event(self, event):
        event_dict = asdict(event)
        if 'time' in event_dict['details']:
            del event_dict['details']['time']
        if 'timestamp' in event_dict:
            del event_dict['timestamp']

        if event_dict['type'] == 'middleclick':
            event_dict['type'] = 'click'
        if event_dict['details']['type'] == 'middleclick':
            event_dict['details']['type'] = 'click'

        if event_dict['type'] == 'input':
            event_dict['details'] = {'value': event_dict['details'].get('value', '')}
        else:
            event_dict['details'] = {'elementDescription': event_dict['details'].get('elementDescription', '')}

        return event_dict

    def save_configuration(self):
        if hasattr(self.configuration, 'file_path'):
            try:
                with open(self.configuration.file_path, 'w') as f:
                    json.dump(self.configuration.data, f, indent=2)
                logger.info(f"Configuration saved to {self.configuration.file_path}")
            except Exception as e:
                logger.error(f"Error saving configuration: {e}")
        else:
            logger.warning("Configuration object has no file_path attribute")


async def inject_event_listener(tab):
    js_code = """
    if (typeof window.recordedEvents === 'undefined') {
        window.recordedEvents = [];
    }
    if (typeof window.lastInputEvent === 'undefined') {
        window.lastInputEvent = {};
    }
    if (typeof window.isProcessingClick === 'undefined') {
        window.isProcessingClick = false;
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

    async function tryClick(element, maxAttempts = 3) {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            try {
                const rect = element.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && isElementVisible(element) && isElementEnabled(element)) {
                    const newEvent = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    element.dispatchEvent(newEvent);
                    return true;
                }
            } catch (error) {
                console.error('Error during click attempt:', error);
            }
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        return false;
    }
    
    function isElementVisible(element) {
        return element.offsetWidth > 0 && element.offsetHeight > 0;
    }
    
    function isElementEnabled(element) {
        return !element.disabled;
    }


    document.addEventListener('mousedown', async function(e) {
        // Проверяем, что нажата средняя кнопка мыши (колесико)
        if (e.button !== 1) {
            return;
        }
    
        if (window.isProcessingClick) {
            return;
        }
        window.isProcessingClick = true;
    
        try {
            e.preventDefault();
            e.stopImmediatePropagation();
    
            const element = e.composedPath()[0];
            const eventData = {
                type: 'middleclick',
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
    
            window.recordedEvents.push(eventData);
            console.log('Middle click event recorded:', JSON.stringify(eventData));
    
            // Отображение визуального эффекта для обработанной кнопки
            element.style.backgroundColor = 'rgba(0, 255, 0, 0.3)';
            setTimeout(() => {
                element.style.backgroundColor = '';
            }, 500);
    
            // Отображение уведомления об обработке кнопки
            const notification = document.createElement('div');
            notification.textContent = 'Middle click processed';
            notification.style.position = 'fixed';
            notification.style.top = '10px';
            notification.style.right = '10px';
            notification.style.padding = '10px';
            notification.style.backgroundColor = 'rgba(0, 255, 0, 0.8)';
            notification.style.color = 'white';
            notification.style.zIndex = '9999';
            document.body.appendChild(notification);
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 1000);
    
            await new Promise(resolve => setTimeout(resolve, 2000));
    
            const clickSuccess = await tryClick(element);
            if (!clickSuccess) {
                console.error('Failed to perform click after multiple attempts');
            }
    
            if (element.tagName.toLowerCase() === 'a' && element.href) {
                window.location.href = element.href;
            }
    
            if (element.tagName.toLowerCase() === 'button' && element.type === 'submit') {
                const form = element.closest('form');
                if (form) {
                    form.submit();
                }
            }
        } catch (error) {
            console.error('Error processing middle click:', error);
        } finally {
            window.isProcessingClick = false;
        }
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
        console.log('Input event recorded:', JSON.stringify(eventData));
        console.log('Current lastInputEvent:', JSON.stringify(window.lastInputEvent));
    }, true);

    console.log('Event listener injected and initialized');
    console.log('window.recordedEvents:', JSON.stringify(window.recordedEvents));
    console.log('window.lastInputEvent:', JSON.stringify(window.lastInputEvent));
    """
    try:
        await tab.evaluate(js_code)
        logger.info(f"Event listener injected successfully for tab: {await tab.evaluate('window.location.href')}")

        # Проверка инициализации
        recorded_events = await tab.evaluate("window.recordedEvents")
        last_input_event = await tab.evaluate("window.lastInputEvent")
        logger.info(f"Initialization check - recordedEvents: {recorded_events}, lastInputEvent: {last_input_event}")
    except Exception as e:
        logger.error(f"Error injecting event listener: {e}")


async def get_recorded_events(tab, max_retries=3):
    for attempt in range(max_retries):
        try:
            events = await tab.evaluate("window.recordedEvents")
            last_input = await tab.evaluate("window.lastInputEvent")

            if events is None:
                events = []
            if last_input is None:
                last_input = {}

            if events:
                await tab.evaluate("window.recordedEvents = []")
            if last_input:
                await tab.evaluate("window.lastInputEvent = {}")

            return events, last_input
        except Exception as e:
            logger.error(f"Error getting recorded events (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
    return [], {}


async def record_events(setup, recorder, stop_event):
    if setup is None:
        logger.error("Setup object is None")
        return []

    browser = setup.browser
    if browser is None:
        logger.error("Browser object is None")
        return []

    main_tab = getattr(browser, 'main_tab', None)
    if main_tab is None:
        logger.error("Main tab is None")
        return []

    try:
        await main_tab.get("https://miles.plumenetwork.xyz/")
        await recorder.tab_manager.add_tab(main_tab)

        logger.info("Recording started. Perform your actions.")
        logger.info("Press 'q' and Enter to stop recording.")

        while not stop_event.is_set():
            try:
                current_tabs = browser.tabs
                for tab in current_tabs:
                    if tab not in recorder.tab_manager.get_all_tabs():
                        await recorder.tab_manager.add_tab(tab)

                for tab in recorder.tab_manager.get_all_tabs():
                    await recorder.process_tab(tab)

                await recorder.tab_manager.remove_inactive_tabs(current_tabs)

            except Exception as loop_error:
                logger.error(f"Error in main loop: {loop_error}")

            await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"Error in record_events: {e}")
        logger.error(traceback.format_exc())

    # Save configuration after recording is finished
    recorder.save_configuration()

    # Return events from configuration
    events = recorder.configuration.data.get('events', [])
    logger.debug(f"Events from configuration: {events}")

    return events


async def input_listener(stop_event):
    while True:
        user_input = await asyncio.get_event_loop().run_in_executor(None, input)
        if user_input.lower() == 'q':
            stop_event.set()
            break
