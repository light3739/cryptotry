import logging

from ..models.configuration import Configuration

logger = logging.getLogger(__name__)


class ConfigurationController:
    def __init__(self, configuration: Configuration, window):
        self.configuration = configuration
        self.window = window
        self.setup_connections()

    def setup_connections(self):
        # Здесь вы можете подключить сигналы от окна к методам контроллера
        pass

    def update_view(self):
        self.window.display_events()

    def add_event(self, event_data):
        logger.debug(f"Adding event: {event_data}")
        self.configuration.add_event(event_data)
        logger.debug(f"Configuration events after adding: {self.configuration.data['events']}")
        self.update_view()

    def remove_event(self, event_data):
        self.configuration.remove_event(event_data)
        self.update_view()

    def update_event(self, old_event_data, new_event_data):
        self.configuration.update_event(old_event_data, new_event_data)
        self.update_view()

    def save_configuration(self):
        self.window.save_configuration()
