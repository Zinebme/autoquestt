import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QListWidget, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class DocumentsView(QWidget):
    def __init__(self, project_data):
        super().__init__()
        self.project_data = project_data
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        title = QLabel("Imported Questionnaires:")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                padding-bottom: 5px;
                border-bottom: 1px solid #ddd;
            }
        """)
        layout.addWidget(title)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e1f0fa;
                color: #0066cc;
            }
        """)
        layout.addWidget(self.file_list)
        self.load_patient_folders()
        font = QFont()
        font.setPointSize(11)  # Increased from default
        self.setFont(font)

    def load_patient_folders(self):
        self.file_list.clear()
        if self.project_data:
            questionnaires = self.project_data.get('compiled_questionnaires', [])
            for q in questionnaires:
                patient_name = os.path.basename(q['patient_dir'])
                self.file_list.addItem(patient_name)

    def update_view(self, project_data):
        self.project_data = project_data
        self.load_patient_folders()
