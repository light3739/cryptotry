import os
import logging
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QFileDialog, QMessageBox, QApplication, \
    QGraphicsScene
from src.models.project import Project
from src.views.project_view import ProjectView

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Event Configuration Manager")
        self.setGeometry(100, 100, 800, 600)  # Уменьшим размер главного окна

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        QApplication.instance().scene = QGraphicsScene()
        self.open_project_button = QPushButton("Open Project")
        self.open_project_button.clicked.connect(self.open_project)
        self.layout.addWidget(self.open_project_button)

        self.project_view = None

    def open_project(self):
        try:
            project_path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
            logger.debug(f"Selected project path: {project_path}")
            if project_path:
                project_name = os.path.basename(project_path)
                logger.debug(f"Project name: {project_name}")
                project = Project(project_name, project_path)
                project.load_configurations()
                logger.debug("Project loaded successfully")

                if self.project_view:
                    self.layout.removeWidget(self.project_view)
                    self.project_view.deleteLater()

                self.project_view = ProjectView(project)
                logger.debug("ProjectView created")
                self.layout.addWidget(self.project_view)
                logger.debug("ProjectView added to layout")
        except Exception as e:
            logger.exception("Error in open_project")
            QMessageBox.critical(self, "Error", f"Failed to open project: {str(e)}")
