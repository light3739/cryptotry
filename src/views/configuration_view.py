from typing import Optional
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene
from ..models.configuration import Configuration
from .event_item import EventItem

logger = logging.getLogger(__name__)


class ConfigurationView(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.layout.addWidget(self.view)
        self.configuration = None

    def set_configuration(self, configuration: Optional[Configuration]):
        self.configuration = configuration
        self.update_view()

    def update_view(self):
        self.scene.clear()
        if self.configuration:
            y_offset = 0
            if isinstance(self.configuration.data, dict):
                events = self.configuration.data.get('events', [])
            elif isinstance(self.configuration.data, list):
                events = self.configuration.data
            else:
                events = []
                logger.warning(f"Unexpected data type for configuration: {type(self.configuration.data)}")

            for event in events:
                event_item = EventItem(event, y_offset)
                self.scene.addItem(event_item)
                y_offset += 100
        else:
            self.scene.addText("No configuration selected")
