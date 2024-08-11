import json
import math
import sys

from PyQt6.QtCore import QPointF, QLineF
from PyQt6.QtGui import QColor, QPolygonF, QPen, QFont, QBrush, QPainter, QLinearGradient
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsScene, QGraphicsView,
                             QVBoxLayout, QWidget, QGraphicsEllipseItem, QGraphicsTextItem,
                             QGraphicsLineItem, QGraphicsItem,
                             QToolTip, QMessageBox, QInputDialog)


class MovableEllipseItem(QGraphicsEllipseItem):
    def __init__(self, x, y, w, h, event_data, parent=None):
        super().__init__(x, y, w, h, parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.event_data = event_data
        self.arrows = []
        self.setAcceptHoverEvents(True)
        self.default_pen = QPen(QColor(100, 100, 100))
        self.hover_pen = QPen(QColor(255, 255, 255))
        self.selected_pen = QPen(QColor(255, 255, 0))
        self.setPen(self.default_pen)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for arrow in self.arrows:
                arrow.updatePosition()
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            self.setPen(self.selected_pen if value else self.default_pen)
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        self.setPen(self.hover_pen)
        QToolTip.showText(event.screenPos(), json.dumps(self.event_data, indent=2))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPen(self.selected_pen if self.isSelected() else self.default_pen)
        QToolTip.hideText()
        super().hoverLeaveEvent(event)


class Arrow(QGraphicsLineItem):
    def __init__(self, startItem, endItem):
        super().__init__()
        self.startItem = startItem
        self.endItem = endItem
        self.startItem.arrows.append(self)
        self.endItem.arrows.append(self)
        self.setZValue(-1000.0)
        self.updatePosition()

    def updatePosition(self):
        line = QLineF(self.mapFromItem(self.startItem, self.startItem.boundingRect().center()),
                      self.mapFromItem(self.endItem, self.endItem.boundingRect().center()))
        self.setLine(line)

    def paint(self, painter, option, widget=None):
        if not self.startItem or not self.endItem:
            return

        gradient = QLinearGradient(self.line().p1(), self.line().p2())
        gradient.setColorAt(0, QColor(100, 100, 100))
        gradient.setColorAt(1, QColor(200, 200, 200))
        painter.setPen(QPen(QBrush(gradient), 2))
        painter.drawLine(self.line())

        # Draw arrowhead
        angle = self.line().angle()
        arrowP1 = self.line().p2() - QPointF(10 * math.cos(math.radians(angle + 30)),
                                             10 * math.sin(math.radians(angle + 30)))
        arrowP2 = self.line().p2() - QPointF(10 * math.cos(math.radians(angle - 30)),
                                             10 * math.sin(math.radians(angle - 30)))

        painter.setBrush(QColor(200, 200, 200))
        painter.drawPolygon(QPolygonF([self.line().p2(), arrowP1, arrowP2]))

    def boundingRect(self):
        return super().boundingRect().adjusted(-10, -10, 10, 10)


from PyQt6.QtCore import Qt, QPoint


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene, event_viewer):
        super().__init__(scene)
        self.event_viewer = event_viewer
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumSize(600, 600)
        self.zoom = 1
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setInteractive(True)
        self.pan_active = False
        self.pan_start = QPoint()
        self.last_mouse_pos = QPoint()
        self.setMouseTracking(True)
        self.space_pressed = False

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom
            factor = 1.1 if event.angleDelta().y() > 0 else 1 / 1.1
            self.zoom *= factor
            self.scale(factor, factor)
        else:
            # Pan
            delta = event.angleDelta() / 8
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.space_pressed:
            item = self.itemAt(event.pos())
            if item is None:
                # Снимаем выделение со всех элементов
                for item in self.scene().selectedItems():
                    item.setSelected(False)
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.pan_active = True
                self.pan_start = event.position().toPoint()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pan_active:
            delta = event.position().toPoint() - self.pan_start
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self.pan_start = event.position().toPoint()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.pan_active:
            self.pan_active = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_items()
        elif event.key() == Qt.Key.Key_Space:
            self.space_pressed = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        elif event.key() == Qt.Key.Key_A:
            self.event_viewer.add_new_event()
        elif event.key() == Qt.Key.Key_C:
            self.event_viewer.change_arrow_connections()
        super().keyPressEvent(event)

    def delete_selected_items(self):
        selected_items = self.scene().selectedItems()
        if not selected_items:
            return

        reply = QMessageBox.question(self, 'Delete Items',
                                     f"Are you sure you want to delete {len(selected_items)} item(s)?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            for item in selected_items:
                if isinstance(item, MovableEllipseItem):
                    # Удаляем связанные стрелки
                    for arrow in item.arrows[:]:
                        self.scene().removeItem(arrow)
                        if arrow.startItem != item:
                            arrow.startItem.arrows.remove(arrow)
                        if arrow.endItem != item:
                            arrow.endItem.arrows.remove(arrow)
                    # Удаляем элемент из JSON
                    self.event_viewer.remove_event(item.event_data)
                    # Удаляем элемент со сцены
                    self.scene().removeItem(item)

            self.event_viewer.save_events()
            self.event_viewer.redraw_scene()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space_pressed = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().keyReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)


class EventViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Recorded Events Viewer")
        self.setGeometry(100, 100, 1000, 800)

        self.setStyleSheet("""
            QMainWindow, QGraphicsView { background-color: #2b2b2b; }
            QToolTip { 
                background-color: #3d3d3d; 
                color: #ffffff; 
                border: 1px solid #5d5d5d;
                font-size: 12px;
            }
        """)

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(self.scene, self)
        layout.addWidget(self.view)

        self.setCentralWidget(main_widget)

        self.load_events()

    def load_events(self):
        try:
            with open('recorded_events.json', 'r') as file:
                self.events = json.load(file)
                self.display_events()
        except FileNotFoundError:
            print("Error: recorded_events.json file not found.")
            self.events = []
        except json.JSONDecodeError:
            print("Error: Invalid JSON in recorded_events.json file.")
            self.events = []

    def save_events(self):
        with open('recorded_events.json', 'w') as file:
            json.dump(self.events, file, indent=2)

    def remove_event(self, event_data):
        event_id = event_data.get('id', str(self.events.index(event_data)))
        self.events.remove(event_data)
        if event_id in self.item_map:
            del self.item_map[event_id]

    def get_event_color(self, event_type):
        color_map = {
            'click': QColor(255, 100, 100),
            'input': QColor(100, 255, 100),
            'Unknown': QColor(150, 150, 150)
        }
        return color_map.get(event_type, QColor(200, 200, 200))

    def redraw_scene(self):
        # Очищаем сцену
        self.scene.clear()
        # Заново отображаем события
        self.display_events()

    def add_new_event(self):
        event_type, ok = QInputDialog.getItem(self, 'New Event', 'Select event type:', ['click', 'input'], 0, False)
        if ok and event_type:
            if event_type == 'click':
                element_description, ok = QInputDialog.getText(self, 'New Event', 'Enter element description:')
                if ok and element_description:
                    url, ok = QInputDialog.getText(self, 'New Event', 'Enter URL:')
                    if ok and url:
                        event_data = {
                            'type': event_type,
                            'elementDescription': element_description,
                            'url': url,
                            'id': str(len(self.events))
                        }
                        self.events.append(event_data)
                        self.save_events()
                        self.redraw_scene()
            elif event_type == 'input':
                value, ok = QInputDialog.getText(self, 'New Event', 'Enter input value:')
                if ok and value:
                    url, ok = QInputDialog.getText(self, 'New Event', 'Enter URL:')
                    if ok and url:
                        event_data = {
                            'type': event_type,
                            'value': value,
                            'url': url,
                            'id': str(len(self.events))
                        }
                        self.events.append(event_data)
                        self.save_events()
                        self.redraw_scene()

    def change_arrow_connections(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 2:
            start_item = selected_items[0]
            end_item = selected_items[1]
            if isinstance(start_item, MovableEllipseItem) and isinstance(end_item, MovableEllipseItem):
                start_event = start_item.event_data
                end_event = end_item.event_data

                # Удаляем старые стрелки
                for arrow in start_item.arrows[:]:
                    if arrow.endItem == end_item:
                        self.scene.removeItem(arrow)
                        start_item.arrows.remove(arrow)
                        end_item.arrows.remove(arrow)

                # Обновляем порядок элементов в JSON
                start_index = self.events.index(start_event)
                end_index = self.events.index(end_event)

                if start_index < end_index:
                    # Перемещаем end_event на позицию после start_event
                    self.events.insert(start_index + 1, self.events.pop(end_index))
                else:
                    # Перемещаем start_event на позицию перед end_event
                    self.events.insert(end_index, self.events.pop(start_index))

                # Создаем новую стрелку
                new_arrow = Arrow(start_item, end_item)
                self.scene.addItem(new_arrow)

                self.save_events()
                self.redraw_scene()

    def display_events(self):
        y_offset = 0
        prev_item = None
        self.item_map = {}  # Словарь для хранения соответствия между event_id и MovableEllipseItem

        for i, event in enumerate(self.events):
            event_id = event.get('id', str(i))  # Используем 'id' из события или создаем свой
            event_type = event.get('type', 'Unknown')
            if event_type == 'input':
                description = f"{event.get('value', 'No value')}"
            else:
                description = event.get('elementDescription', 'No description')

            text = f"{event_type}\n{description[:20]}..."

            ellipse = MovableEllipseItem(0, y_offset, 150, 80, event)
            ellipse.setBrush(self.get_event_color(event_type))
            ellipse.setPen(QPen(QColor(100, 100, 100)))

            text_item = QGraphicsTextItem(text, ellipse)
            text_item.setDefaultTextColor(QColor(0, 0, 0))
            text_item.setFont(QFont("Arial", 8))
            text_rect = text_item.boundingRect()
            text_x = ellipse.boundingRect().center().x() - text_rect.width() / 2
            text_y = ellipse.boundingRect().center().y() - text_rect.height() / 2
            text_item.setPos(text_x, text_y)

            self.scene.addItem(ellipse)
            self.item_map[event_id] = ellipse

            if prev_item:
                arrow = Arrow(prev_item, ellipse)
                self.scene.addItem(arrow)

            prev_item = ellipse
            y_offset += 100

        self.save_events()

        # Устанавливаем размер сцены намного больше, чем фактическое содержимое
        rect = self.scene.itemsBoundingRect()
        expanded_rect = rect.adjusted(-1000, -1000, 1000, 1000)
        self.scene.setSceneRect(expanded_rect)
        self.scene.setBackgroundBrush(QBrush(QColor(43, 43, 43)))

        # Центрируем вид на фактическом содержимом
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self.view.centerOn(rect.center())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = EventViewer()
    viewer.show()
    sys.exit(app.exec())
