import asyncio
import json
import logging
import math
import traceback

from PyQt6.QtCore import QPointF, QLineF, Qt, QPoint, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPolygonF, QPen, QFont, QBrush, QPainter, QLinearGradient
from PyQt6.QtWidgets import (QMainWindow, QGraphicsScene, QGraphicsView,
                             QVBoxLayout, QWidget, QGraphicsEllipseItem, QGraphicsTextItem,
                             QGraphicsLineItem, QGraphicsItem,
                             QToolTip, QMessageBox, QInputDialog, QPushButton)

from src.controllers.configuration_controller import ConfigurationController
from src.utils.record import EventRecorder, record_events
from src.utils.undetected import UndetectedSetup

logger = logging.getLogger(__name__)


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


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene, configuration_window):
        super().__init__(scene)
        self.configuration_window = configuration_window
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
            self.configuration_window.add_new_event()
        elif event.key() == Qt.Key.Key_C:
            self.configuration_window.change_arrow_connections()
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
                    # Удаляем элемент из конфигурации
                    self.configuration_window.remove_event(item.event_data)
                    # Удаляем элемент со сцены
                    self.scene().removeItem(item)

            self.configuration_window.save_configuration()
            self.configuration_window.display_events()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space_pressed = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().keyReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)


class RecordThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, configuration):
        super().__init__()
        self.configuration = configuration

    def run(self):
        try:
            proxy = {
                'host': '45.13.195.53',
                'port': '30001',
                'user': 'vintarik8_gmail_com',
                'pass': 'c560667e15'
            }
            logger.debug("Creating UndetectedSetup object...")
            setup = UndetectedSetup("my_profile", proxy=proxy)
            logger.debug(f"UndetectedSetup object created: {setup}")

            logger.debug("Initializing driver...")
            asyncio.run(setup.initialize_driver())
            logger.debug("Driver initialized")

            if setup.browser is None:
                raise ValueError("Browser is None after initialization")

            if setup.main_tab is None:
                raise ValueError("Main tab is None after initialization")

            logger.debug("Creating EventRecorder object...")
            recorder = EventRecorder(self.configuration)
            logger.debug("EventRecorder object created")

            stop_event = asyncio.Event()

            logger.debug("Starting record_events...")
            events = asyncio.run(record_events(setup, recorder, stop_event))
            logger.debug(f"Recorded events in RecordThread: {events}")
            self.finished.emit(events)
        except Exception as e:
            logger.error(f"Error in RecordThread: {e}")
            logger.error(traceback.format_exc())
            self.error.emit(str(e))
        finally:
            if setup and setup.browser:
                asyncio.run(setup.close_browser())

    async def record_events(self, setup, recorder, stop_event):
        try:
            await setup.initialize_driver()
            events = await record_events(setup, recorder, stop_event)
            return events
        finally:
            if setup.browser:
                await setup.close_browser()


class ConfigurationWindow(QMainWindow):
    def __init__(self, configuration):
        super().__init__()
        self.configuration = configuration
        self.configuration_controller = ConfigurationController(configuration, self)
        self.setWindowTitle(f"Configuration: {configuration.name}")
        self.setGeometry(100, 100, 1000, 800)
        self.auto_save_timer = QTimer(self)

        self.auto_save_timer.timeout.connect(self.save_configuration)
        self.auto_save_timer.start(5000)  # Сохранение каждые 5 секунд
        self.setStyleSheet("""
            QMainWindow, QGraphicsView { background-color: #2b2b2b; }
            QToolTip { 
                background-color: #3d3d3d; 
                color: #ffffff; 
                border: 1px solid #5d5d5d;
                font-size: 12px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 15px 32px;
                text-align: center;
                text-decoration: none;
                font-size: 16px;
                margin: 4px 2px;
                cursor: pointer;
            }
        """)

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(self.scene, self)
        layout.addWidget(self.view)

        self.record_button = QPushButton("Record")
        self.record_button.clicked.connect(self.start_recording)
        layout.addWidget(self.record_button)

        self.setCentralWidget(main_widget)

        self.display_events()

    def start_recording(self):
        self.record_thread = RecordThread(self.configuration)
        self.record_thread.finished.connect(self.on_recording_finished)
        self.record_thread.error.connect(self.on_recording_error)
        self.record_thread.start()
        self.record_button.setEnabled(False)
        self.record_button.setText("Recording...")

    def on_recording_finished(self, events):
        self.record_button.setEnabled(True)
        self.record_button.setText("Record")
        logger.debug(f"Received events in on_recording_finished: {events}")

        # Проверяем и преобразуем формат событий
        formatted_events = []
        for event in events:
            if event['type'] == 'input':
                event['details'] = {'value': event['details'].get('value', '')}
            else:
                event['details'] = {'elementDescription': event['details'].get('elementDescription', '')}
            formatted_events.append(event)

        logger.debug(f"Formatted events in on_recording_finished: {formatted_events}")
        self.update_events(formatted_events)
        self.save_configuration()
        QMessageBox.information(self, "Recording Finished",
                                f"The recording has been completed successfully. {len(events)} events recorded.")

    def on_recording_error(self, error_message):
        self.record_button.setEnabled(True)
        self.record_button.setText("Record")
        QMessageBox.critical(self, "Recording Error", f"An error occurred during recording: {error_message}")

    def get_event_color(self, event_type):
        color_map = {
            'click': QColor(255, 100, 100),
            'input': QColor(100, 255, 100),
            'elementAdded': QColor(100, 100, 255),
            'Unknown': QColor(150, 150, 150)
        }
        return color_map.get(event_type, QColor(200, 200, 200))

    def display_events(self):
        self.scene.clear()
        y_offset = 0
        prev_item = None

        for event in self.configuration.data.get('events', []):
            event_type = event.get('type', 'Unknown')
            details = event.get('details', {})

            if event_type == 'input':
                description = f"{details.get('value', 'No value')}"
            else:
                description = details.get('elementDescription', 'No description')

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

            if prev_item:
                arrow = Arrow(prev_item, ellipse)
                self.scene.addItem(arrow)

            prev_item = ellipse
            y_offset += 100

        # Устанавливаем размер сцены намного больше, чем фактическое содержимое
        rect = self.scene.itemsBoundingRect()
        expanded_rect = rect.adjusted(-1000, -1000, 1000, 1000)
        self.scene.setSceneRect(expanded_rect)
        self.scene.setBackgroundBrush(QBrush(QColor(43, 43, 43)))

        # Центрируем вид на фактическом содержимом
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self.view.centerOn(rect.center())

    def remove_event(self, event_data):
        events = self.configuration.data.get('events', [])
        events = [e for e in events if e != event_data]
        self.configuration.data['events'] = events
        self.save_configuration()

    def update_events(self, new_events):
        logger.debug(f"Updating events with: {new_events}")
        for event in new_events:
            self.configuration_controller.add_event(event)
        logger.debug(f"Updated configuration events: {self.configuration.data['events']}")
        self.configuration_controller.save_configuration()
        self.configuration_controller.update_view()

    def set_configuration(self, configuration):
        self.configuration = configuration
        self.display_events()

    def save_configuration(self):
        if hasattr(self.configuration, 'file_path'):
            try:
                logger.debug(f"Saving configuration data: {self.configuration.data}")
                formatted_events = []
                for event in self.configuration.data['events']:
                    if event['type'] == 'input':
                        event['details'] = {'value': event['details']['value']}
                    else:
                        event['details'] = {'elementDescription': event['details']['elementDescription']}
                    formatted_events.append(event)

                self.configuration.data['events'] = formatted_events

                # Логируем путь к файлу и данные, которые будут сохранены
                logger.debug(f"Saving configuration to file: {self.configuration.file_path}")
                logger.debug(f"Configuration data to save: {self.configuration.data}")

                with open(self.configuration.file_path, 'w') as f:
                    json.dump(self.configuration.data, f, indent=2)
                logger.info(f"Configuration saved to {self.configuration.file_path}")
            except Exception as e:
                logger.error(f"Error saving configuration: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.warning("Configuration object has no file_path attribute")

    def add_new_event(self):
        event_type, ok = QInputDialog.getItem(self, 'New Event', 'Select event type:',
                                              ['click', 'input', 'elementAdded'], 0, False)
        if ok and event_type:
            url, ok = QInputDialog.getText(self, 'New Event', 'Enter URL:')
            if ok and url:
                details = {}
                if event_type in ['click', 'elementAdded']:
                    element_description, ok = QInputDialog.getText(self, 'New Event', 'Enter element description:')
                    if ok and element_description:
                        details = {
                            'type': event_type,
                            'tagName': 'BUTTON',  # Пример, можно изменить
                            'elementDescription': element_description
                        }
                elif event_type == 'input':
                    value, ok = QInputDialog.getText(self, 'New Event', 'Enter input value:')
                    if ok and value:
                        details = {
                            'type': event_type,
                            'tagName': 'INPUT',  # Пример, можно изменить
                            'value': value
                        }

                if details:
                    event_data = {
                        'type': event_type,
                        'url': url,
                        'details': details
                    }
                    self.configuration.data.get('events', []).append(event_data)
                    self.save_configuration()
                    self.display_events()

    def change_arrow_connections(self):
        selected_items = self.scene.selectedItems()
        if len(selected_items) == 2:
            start_item, end_item = selected_items
            if isinstance(start_item, MovableEllipseItem) and isinstance(end_item, MovableEllipseItem):
                start_event = start_item.event_data
                end_event = end_item.event_data

                # Удаляем старые стрелки
                for arrow in start_item.arrows[:]:
                    if arrow.endItem == end_item:
                        self.scene.removeItem(arrow)
                        start_item.arrows.remove(arrow)
                        end_item.arrows.remove(arrow)

                # Обновляем порядок элементов в конфигурации
                events = self.configuration.data.get('events', [])
                start_index = events.index(start_event)
                end_index = events.index(end_event)

                if start_index < end_index:
                    events.insert(start_index + 1, events.pop(end_index))
                else:
                    events.insert(end_index, events.pop(start_index))

                self.configuration.data['events'] = events

                # Создаем новую стрелку
                new_arrow = Arrow(start_item, end_item)
                self.scene.addItem(new_arrow)

                self.save_configuration()
                self.display_events()
