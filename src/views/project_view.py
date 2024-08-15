from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QInputDialog, QMessageBox
from PyQt6.QtCore import pyqtSignal

from src.models.configuration import Configuration
from src.models.project import Project
from src.views.configuration_view import ConfigurationView

import logging

logger = logging.getLogger(__name__)


class ProjectView(QWidget):
    configuration_selected = pyqtSignal(object)  # Определяем сигнал здесь

    def __init__(self, project: Project):
        super().__init__()
        logger.debug("Initializing ProjectView")
        self.project = project
        self.layout = QVBoxLayout(self)

        self.config_list = QListWidget()
        self.layout.addWidget(self.config_list)
        logger.debug("Added config_list to layout")

        self.button_layout = QHBoxLayout()
        self.add_config_button = QPushButton("Add Configuration")
        self.remove_config_button = QPushButton("Remove Configuration")
        self.button_layout.addWidget(self.add_config_button)
        self.button_layout.addWidget(self.remove_config_button)
        self.layout.addLayout(self.button_layout)
        logger.debug("Added buttons to layout")

        self.config_view = ConfigurationView()
        self.layout.addWidget(self.config_view)
        logger.debug("Added ConfigurationView to layout")

        self.update_config_list()
        logger.debug("Updated config list")
        self.setup_connections()
        logger.debug("Setup connections completed")

    def update_config_list(self):
        try:
            self.config_list.clear()
            for config in self.project.configurations:
                self.config_list.addItem(config.name)
            logger.debug(f"Updated config list. Current configurations: {[c.name for c in self.project.configurations]}")
        except Exception as e:
            logger.exception("Error in update_config_list")
            QMessageBox.critical(self, "Error", f"Failed to update configuration list: {str(e)}")


    def refresh_view(self):
        try:
            self.update_config_list()
            if self.project.configurations:
                self.config_list.setCurrentRow(0)
                current_item = self.config_list.item(0)
                if current_item:
                    self.on_config_selected(current_item, None)
                else:
                    self.config_view.set_configuration(None)
            else:
                self.config_view.set_configuration(None)
                self.config_list.clear()
            logger.debug("View refreshed successfully")
        except Exception as e:
            logger.exception("Error in refresh_view")
            QMessageBox.critical(self, "Error", f"Failed to refresh view: {str(e)}")



    def setup_connections(self):
        self.config_list.currentItemChanged.connect(self.on_config_selected)  # type: ignore
        self.add_config_button.clicked.connect(self.add_configuration)  # type: ignore
        self.remove_config_button.clicked.connect(self.remove_configuration)  # type: ignore

    def on_config_selected(self, current, previous):
        if current:
            row = self.config_list.row(current)
            if 0 <= row < len(self.project.configurations):
                config = self.project.configurations[row]
                self.config_view.set_configuration(config)
                self.configuration_selected.emit(config)
            else:
                logger.warning(f"Invalid configuration index: {row}")
                self.config_view.set_configuration(None)
        else:
            self.config_view.set_configuration(None)

    def add_configuration(self):
        name, ok = QInputDialog.getText(self, 'New Configuration', 'Enter configuration name:')
        if ok and name:
            new_config = Configuration(name, {'events': []})
            self.project.add_configuration(new_config)
            self.update_config_list()
            logger.debug(f"Added new configuration: {name}")


    def remove_configuration(self):
        try:
            current_item = self.config_list.currentItem()
            if current_item:
                config_name = current_item.text()
                reply = QMessageBox.question(self, 'Remove Configuration',
                                             f"Are you sure you want to remove '{config_name}'?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    config_to_remove = next((c for c in self.project.configurations if c.name == config_name), None)
                    if config_to_remove:
                        logger.debug(f"Attempting to remove configuration: {config_name}")
                        self.project.remove_configuration(config_to_remove)
                        logger.debug(f"Configuration removed from project: {config_name}")
                        self.refresh_view()
                        logger.debug(f"View refreshed after removing: {config_name}")
                    else:
                        logger.warning(f"Configuration {config_name} not found in project")
                        QMessageBox.warning(self, 'Remove Configuration', f"Configuration '{config_name}' not found.")
            else:
                QMessageBox.warning(self, 'Remove Configuration', "Please select a configuration to remove.")
        except Exception as e:
            logger.exception("Error in remove_configuration")
            QMessageBox.critical(self, "Error", f"Failed to remove configuration: {str(e)}")
