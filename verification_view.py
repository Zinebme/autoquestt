from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QVBoxLayout, QPushButton, QScrollArea,
    QSplitter, QFrame, QSizePolicy, QMessageBox
)
from PyQt5.QtGui import QPixmap, QColor, QFont, QIcon
from PyQt5.QtCore import Qt, QRect, QPoint
import os
import re


class VerificationView(QWidget):
    def __init__(self, project_data, save_callback):
        super().__init__()
        self.project_data = project_data
        self.save_callback = save_callback
        self.current_zoom = 100
        self.current_patient = None
        self.current_page_index = 0
        self.current_images = []
        self.image_viewer_visible = False
        self.initUI()

    # verification_view.py (modifications dans initUI)
    def initUI(self):
        # Main splitter for resizable panels
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #dcdcdc;
            }
        """)

        # --- Left panel - Table ---
        self.table_panel = QFrame()
        self.table_panel.setFrameShape(QFrame.NoFrame)
        table_layout = QVBoxLayout(self.table_panel)
        table_layout.setContentsMargins(25, 25, 25, 25)
        table_layout.setSpacing(15)

        title = QLabel("Vérification des Données")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #333333;")
        table_layout.addWidget(title)

        self.toggle_btn = QPushButton("Afficher la visualisation")
        self.toggle_btn.clicked.connect(self.toggle_viewer)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #3c4043;
                border: 1px solid #dcdcdc;
                padding: 8px 15px;
                min-width: 180px;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
        """)
        table_layout.addWidget(self.toggle_btn, alignment=Qt.AlignLeft)

        # Data table
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.AllEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                font-size: 11pt;
                gridline-color: #e8eaed;
                color: #333333;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 12px;
                border: 1px solid #dcdcdc;
                font-weight: bold;
                color: #333333;
            }
            QTableWidget::item {
                padding: 10px;
                color: #333333;
            }
            QTableWidget::item:selected {
                background-color: #e8f0fe;
                color: #1967d2;
            }
        """)
        table_layout.addWidget(self.table)

        # --- Right panel - Image Viewer ---
        self.viewer_panel = QFrame()
        self.viewer_panel.setFrameShape(QFrame.NoFrame)
        viewer_layout = QVBoxLayout(self.viewer_panel)
        viewer_layout.setContentsMargins(25, 25, 25, 25)
        viewer_layout.setSpacing(15)

        viewer_title = QLabel("Visualisation du Document")
        viewer_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        viewer_title.setStyleSheet("color: #333333;")
        viewer_layout.addWidget(viewer_title)

        # Viewer controls
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.prev_btn = QPushButton("Précédent")
        self.next_btn = QPushButton("Suivant")
        self.page_label = QLabel("Page : -/-")
        self.page_label.setStyleSheet("color: #333333;")
        self.zoom_in_btn = QPushButton("+")
        self.zoom_out_btn = QPushButton("-")

        button_style = """
            QPushButton {
                background-color: #f1f3f4;
                color: #3c4043;
                border: 1px solid #dcdcdc;
                padding: 8px 12px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
        """
        self.prev_btn.setStyleSheet(button_style)
        self.next_btn.setStyleSheet(button_style)
        self.zoom_in_btn.setStyleSheet(button_style + "min-width: 40px;")
        self.zoom_out_btn.setStyleSheet(button_style + "min-width: 40px;")

        controls.addWidget(self.prev_btn)
        controls.addWidget(self.page_label)
        controls.addWidget(self.next_btn)
        controls.addStretch()
        controls.addWidget(self.zoom_out_btn)
        controls.addWidget(self.zoom_in_btn)
        viewer_layout.addLayout(controls)

        # Image display
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                background-color: #ffffff;
            }
        """)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #ffffff; padding: 10px;")
        self.scroll_area.setWidget(self.image_label)
        viewer_layout.addWidget(self.scroll_area)

        # --- Main Layout Setup ---
        self.main_splitter.addWidget(self.table_panel)
        self.main_splitter.addWidget(self.viewer_panel)
        self.main_splitter.setSizes([self.width(), 0])
        self.viewer_panel.hide()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.main_splitter)
        self.setLayout(main_layout)

        # Connections
        self.table.selectionModel().selectionChanged.connect(self.on_row_selected)
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.table.cellChanged.connect(self.on_cell_changed)

        self.load_data()

    def toggle_viewer(self):
        """Toggle image viewer visibility"""
        if self.table.currentRow() < 0 and not self.current_patient:
            CustomMessageBox.warning(self, "Aucune sélection", "Veuillez sélectionner un patient dans le tableau.")
            return

        self.image_viewer_visible = not self.image_viewer_visible

        if self.image_viewer_visible:
            self.viewer_panel.show()
            self.main_splitter.setSizes([self.width() // 2, self.width() // 2])
            if self.current_patient:
                self.show_current_page()
            self.toggle_btn.setText("Masquer la visualisation")
            self.toggle_btn.setIcon(QIcon("icons/visibility_off.png"))
        else:
            self.viewer_panel.hide()
            self.main_splitter.setSizes([self.width(), 0])
            self.toggle_btn.setText("Afficher la visualisation")
            self.toggle_btn.setIcon(QIcon("icons/visibility.png"))

    def load_data(self):
        self.table.blockSignals(True)
        try:
            self.table.clear()

            if not self.project_data.get('extracted_data'):
                return

            # Setup headers
            headers = ["Patient"] + [v['name'] if isinstance(v, dict) else str(v)
                                     for v in self.project_data.get('variables', [])] + ["Erreurs"]
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)

            # Populate rows
            for row, (patient_id, data) in enumerate(self.project_data['extracted_data'].items()):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(patient_id))

                for col, var in enumerate(self.project_data['variables'], start=1):
                    value = str(data["data"]["variables"].get(var['name'] if isinstance(var, dict) else var, ""))
                    item = QTableWidgetItem(value)
                    if '?' in value:
                        item.setBackground(QColor("#fce8e6")) # Soft red for attention
                    self.table.setItem(row, col, item)

                errors = "\n".join(data["data"].get("errors", []))
                if data.get("error"):
                    errors += f"\n{data['error']}"
                self.table.setItem(row, len(headers) - 1, QTableWidgetItem(errors))

        finally:
            self.table.blockSignals(False)
            self.table.resizeColumnsToContents()

    def on_row_selected(self):
        """When a row is selected in the table"""
        selected = self.table.selectedItems()
        if not selected:
            return

        patient_id = self.table.item(selected[0].row(), 0).text()

        for patient in self.project_data['compiled_questionnaires']:
            if os.path.basename(patient['patient_dir']) == patient_id:
                self.current_patient = patient
                self.current_page_index = 0
                self.current_images = sorted(
                    [f for f in os.listdir(patient['patient_dir'])
                     if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
                    key=lambda x: [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', x)]
                )
                if self.image_viewer_visible:
                    self.show_current_page()
                break

    def show_current_page(self):
        """Display current page image"""
        if not self.current_patient or not self.current_images:
            self.image_label.setText("Aucune image disponible")
            return

        img_path = os.path.join(self.current_patient['patient_dir'],
                                self.current_images[self.current_page_index])
        pixmap = QPixmap(img_path)

        if pixmap.isNull():
            self.image_label.setText("Image non valide")
            return

        scaled = pixmap.scaledToWidth(int(pixmap.width() * (self.current_zoom / 100)))
        self.image_label.setPixmap(scaled)
        self.page_label.setText(f"Page: {self.current_page_index + 1}/{len(self.current_images)}")
        self.prev_btn.setEnabled(self.current_page_index > 0)
        self.next_btn.setEnabled(self.current_page_index < len(self.current_images) - 1)

    def prev_page(self):
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.show_current_page()

    def next_page(self):
        if self.current_page_index < len(self.current_images) - 1:
            self.current_page_index += 1
            self.show_current_page()

    def zoom_in(self):
        self.current_zoom = min(300, self.current_zoom + 25)
        self.show_current_page()

    def zoom_out(self):
        self.current_zoom = max(50, self.current_zoom - 25)
        self.show_current_page()

    def on_cell_changed(self, row, column):
        """Handle data edits"""
        try:
            patient_id = self.table.item(row, 0).text()
            var_name = self.table.horizontalHeaderItem(column).text()
            new_value = self.table.item(row, column).text()

            if patient_id in self.project_data['extracted_data']:
                self.project_data['extracted_data'][patient_id]["data"]["variables"][var_name] = new_value
                self.save_callback()
        except Exception as e:
            print(f"Error saving change: {e}")

    def update_view(self, project_data=None):
        """Refresh view with new data"""
        if project_data:
            self.project_data = project_data
        self.load_data()
