import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class Configuration:
    def __init__(self, name: str, data: Dict[str, Any], file_path: str):
        self.name = name
        self.data = data if isinstance(data, dict) else {'events': data if isinstance(data, list) else []}
        self.file_path = file_path

    def add_event(self, event: Dict[str, Any]):
        logger.debug(f"Adding event to configuration: {event}")
        if 'events' not in self.data:
            self.data['events'] = []
        self.data['events'].append(event)
        logger.debug(f"Configuration events after adding: {self.data['events']}")

    def remove_event(self, event: Dict[str, Any]):
        logger.debug(f"Removing event: {event}")
        if 'events' in self.data:
            self.data['events'].remove(event)

    def update_event(self, old_event: Dict[str, Any], new_event: Dict[str, Any]):
        logger.debug(f"Updating event: {old_event} -> {new_event}")
        if 'events' in self.data:
            index = self.data['events'].index(old_event)
            self.data['events'][index] = new_event
