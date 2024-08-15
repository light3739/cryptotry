from ..models.configuration import Configuration
from ..views.configuration_view import ConfigurationView


class ConfigurationController:
    def __init__(self, configuration: Configuration, view: ConfigurationView):
        self.configuration = configuration
        self.view = view
        self.setup_connections()

    def setup_connections(self):
        # Здесь вы можете подключить сигналы от view к методам контроллера
        pass

    def update_view(self):
        self.view.set_configuration(self.configuration)

    def add_event(self, event_data):
        self.configuration.add_event(event_data)
        self.update_view()

    def remove_event(self, event_data):
        self.configuration.remove_event(event_data)
        self.update_view()

    def update_event(self, old_event_data, new_event_data):
        self.configuration.update_event(old_event_data, new_event_data)
        self.update_view()

    def save_configuration(self):
        # Здесь может быть логика сохранения конфигурации
        pass
