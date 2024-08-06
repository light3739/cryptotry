import sys
import json
from PyQt6.QtWidgets import QApplication, QMainWindow, QListWidget, QTextEdit, QSplitter, QVBoxLayout, QWidget


class EventViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Recorded Events Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Create main widget and layout
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Create splitter for list and details
        splitter = QSplitter()

        # Create list widget
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.show_event_details)

        # Create text edit for details
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)

        # Add widgets to splitter
        splitter.addWidget(self.list_widget)
        splitter.addWidget(self.details_text)

        # Add splitter to layout
        layout.addWidget(splitter)

        # Set main widget
        self.setCentralWidget(main_widget)

        # Load events
        self.load_events()

    def load_events(self):
        try:
            with open('recorded_events.json', 'r') as file:
                self.events = json.load(file)
                for i, event in enumerate(self.events):
                    event_type = event.get('type', 'Unknown')
                    description = event.get('elementDescription', 'No description')
                    self.list_widget.addItem(f"Event {i + 1}: {event_type} - {description}")
        except FileNotFoundError:
            self.details_text.setText("Error: recorded_events.json file not found.")
        except json.JSONDecodeError:
            self.details_text.setText("Error: Invalid JSON in recorded_events.json file.")

    def show_event_details(self, item):
        index = self.list_widget.row(item)
        event = self.events[index]
        details = "\n".join(f"{k}: {v}" for k, v in event.items())
        self.details_text.setText(details)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = EventViewer()
    viewer.show()
    sys.exit(app.exec())
