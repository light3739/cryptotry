from typing import Dict, Any


class Configuration:
    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data if isinstance(data, dict) else {'events': data if isinstance(data, list) else []}

    def add_event(self, event: Dict[str, Any]):
        if 'events' not in self.data:
            self.data['events'] = []
        self.data['events'].append(event)

    def remove_event(self, event: Dict[str, Any]):
        if 'events' in self.data:
            self.data['events'].remove(event)

    def update_event(self, old_event: Dict[str, Any], new_event: Dict[str, Any]):
        if 'events' in self.data:
            index = self.data['events'].index(old_event)
            self.data['events'][index] = new_event
