from typing import Optional
import logging

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, QDialog, QTextEdit, QPushButton
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
        self.view.viewport().installEventFilter(self)

    def set_configuration(self, configuration: Optional[Configuration]):
        self.configuration = configuration
        # Не обновляем вид здесь, только сохраняем конфигурацию

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

    def eventFilter(self, obj, event):
        if obj == self.view.viewport():
            if event.type() == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
                self.open_json_editor()
                return True
        return super().eventFilter(obj, event)

    def open_json_editor(self):
        if self.configuration:
            dialog = JsonEditorDialog(self.configuration.data)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.configuration.data = dialog.get_json_data()
                self.update_view()


class JsonEditorDialog(QDialog):
    def __init__(self, json_data):
        super().__init__()
        self.setWindowTitle("JSON Editor")
        self.layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(str(json_data))
        self.layout.addWidget(self.text_edit)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        self.layout.addWidget(self.save_button)

    def get_json_data(self):
        return eval(self.text_edit.toPlainText())
