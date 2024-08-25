import os
import json
from typing import List
from .configuration import Configuration
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Project:
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.configurations: List[Configuration] = []

    def load_configurations(self):
        self.configurations = []
        logger.debug(f"Loading configurations from {self.path}")
        for filename in os.listdir(self.path):
            if filename.endswith('.json'):
                file_path = os.path.join(self.path, filename)
                logger.debug(f"Processing file: {file_path}")
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    config_name = os.path.splitext(filename)[0]  # Remove .json extension
                    logger.debug(f"Loaded data for configuration: {config_name}")
                    self.configurations.append(Configuration(config_name, data, file_path))
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {str(e)}")
        logger.debug(f"Loaded {len(self.configurations)} configurations")

    def save_configurations(self):
        for config in self.configurations:
            file_path = os.path.join(self.path, f"{config.name}.json")
            with open(file_path, 'w') as f:
                json.dump(config.data, f, indent=2)
        logger.debug(f"Saved {len(self.configurations)} configurations")

    def add_configuration(self, config):
        file_path = os.path.join(self.path, f"{config.name}.json")
        config.file_path = file_path  # Добавляем file_path к конфигурации
        self.configurations.append(config)
        self.save_configurations()

    def remove_configuration(self, config):
        try:
            if config in self.configurations:
                self.configurations.remove(config)
                file_path = os.path.join(self.path, f"{config.name}.json")
                if os.path.exists(file_path):
                    os.remove(file_path)
                self.save_configurations()
                logger.debug(f"Removed configuration: {config.name}")
            else:
                logger.warning(f"Configuration {config.name} not found in project")
        except Exception as e:
            logger.exception(f"Error removing configuration {config.name}")
            raise

    def reorder_configurations(self, new_order: List[int]):
        self.configurations = [self.configurations[i] for i in new_order]
