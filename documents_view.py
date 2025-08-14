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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Apply modern styling
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #495057;
            }
            QListWidget {
                background-color: white;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #f1f3f4;
                border-radius: 6px;
                margin: 2px 0;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
        """)

        title = QLabel("📄 Questionnaires Importés")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #495057; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Info label
        info_label = QLabel("Liste des dossiers patients organisés par questionnaire")
        info_label.setStyleSheet("color: #6c757d; font-size: 11px; margin-bottom: 15px;")
        layout.addWidget(info_label)

        self.file_list = QListWidget()
        layout.addWidget(self.file_list)
        self.load_patient_folders()

    def load_patient_folders(self):
        self.file_list.clear()
        if self.project_data:
            questionnaires = self.project_data.get('compiled_questionnaires', [])
            if not questionnaires:
                # Add placeholder item
                placeholder = QListWidgetItem("Aucun questionnaire importé")
                placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsSelectable)
                self.file_list.addItem(placeholder)
                return
                
            for q in questionnaires:
                patient_name = os.path.basename(q['patient_dir'])
                item = QListWidgetItem(f"👤 {patient_name}")
                self.file_list.addItem(item)

    def update_view(self, project_data):
        self.project_data = project_data
        self.load_patient_folders()

