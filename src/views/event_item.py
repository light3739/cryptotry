from PyQt6.QtWidgets import QGraphicsItem, QGraphicsTextItem
from PyQt6.QtGui import QColor, QPen, QBrush
from PyQt6.QtCore import QRectF

class EventItem(QGraphicsItem):
    def __init__(self, event_data, y_offset):
        super().__init__()
        self.event_data = event_data
        self.setPos(0, y_offset)

    def boundingRect(self):
        return QRectF(0, 0, 150, 80)

    def paint(self, painter, option, widget=None):
        painter.setPen(QPen(QColor(100, 100, 100)))
        painter.setBrush(QBrush(self.get_event_color()))
        painter.drawEllipse(self.boundingRect())

        text = QGraphicsTextItem(self.get_event_text(), self)
        text.setPos(10, 10)

    def get_event_color(self):
        event_type = self.event_data.get('type', 'Unknown')
        color_map = {
            'click': QColor(255, 100, 100),
            'input': QColor(100, 255, 100),
            'elementAdded': QColor(100, 100, 255),
            'Unknown': QColor(150, 150, 150)
        }
        return color_map.get(event_type, QColor(200, 200, 200))

    def get_event_text(self):
        event_type = self.event_data.get('type', 'Unknown')
        details = self.event_data.get('details', {})
        if event_type == 'input':
            description = f"{details.get('value', 'No value')}"
        else:
            description = details.get('elementDescription', 'No description')
        return f"{event_type}\n{description[:20]}..."
