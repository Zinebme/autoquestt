from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QVBoxLayout, QPushButton, QScrollArea,
    QSplitter, QFrame, QSizePolicy, QMessageBox
)
from PyQt5.QtGui import QPixmap, QColor, QFont
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

    def initUI(self):
        # Main splitter for resizable panels
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setStyleSheet("QSplitter::handle { background: #ddd; }")

        # Left panel - Table
        self.table_panel = QFrame()
        self.table_panel.setFrameShape(QFrame.StyledPanel)
        table_layout = QVBoxLayout(self.table_panel)
        table_layout.setContentsMargins(5, 5, 5, 5)
        table_layout.setSpacing(10)

        # Control button
        self.toggle_btn = QPushButton("Show Visualization")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_viewer)
        table_layout.addWidget(self.toggle_btn)

        # Data table
        self.table = QTableWidget()
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #ddd;
                gridline-color: #eee;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #ddd;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e1f0fa;
                color: #0066cc;
            }
        """)
        self.table.setEditTriggers(QTableWidget.AllEditTriggers)
        table_layout.addWidget(self.table)

        # Right panel - Image Viewer
        self.viewer_panel = QFrame()
        self.viewer_panel.setFrameShape(QFrame.StyledPanel)
        viewer_layout = QVBoxLayout(self.viewer_panel)
        viewer_layout.setContentsMargins(5, 5, 5, 5)
        viewer_layout.setSpacing(10)

        # Viewer controls
        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.prev_btn = QPushButton("◀ Previous")
        self.next_btn = QPushButton("Next ▶")
        self.page_label = QLabel("Page: -/-")
        self.zoom_in_btn = QPushButton("Zoom +")
        self.zoom_out_btn = QPushButton("Zoom -")

        for btn in [self.prev_btn, self.next_btn, self.zoom_in_btn, self.zoom_out_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #ddd;
                    padding: 5px 10px;
                    border-radius: 4px;
                    min-width: 60px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)

        controls.addWidget(self.prev_btn)
        controls.addWidget(self.page_label)
        controls.addWidget(self.next_btn)
        controls.addStretch()
        controls.addWidget(self.zoom_out_btn)
        controls.addWidget(self.zoom_in_btn)

        viewer_layout.addLayout(controls)

        # Image display
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background: #f0f0f0;")
        self.scroll_area.setWidgetResizable(True)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        viewer_layout.addWidget(self.scroll_area)

        # Add panels to splitter
        self.main_splitter.addWidget(self.table_panel)
        self.main_splitter.addWidget(self.viewer_panel)
        self.main_splitter.setSizes([self.width(), 0])  # Start with viewer hidden

        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.main_splitter)
        self.setLayout(main_layout)

        # Connections
        self.table.selectionModel().selectionChanged.connect(self.on_row_selected)
        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.table.cellChanged.connect(self.on_cell_changed)

        # Initial load
        self.load_data()
        self.viewer_panel.hide()
        font = QFont()
        font.setPointSize(11)  # Increased from default
        self.setFont(font)

    def toggle_viewer(self):
        """Toggle image viewer visibility"""
        if not self.current_patient:
            QMessageBox.warning(self, "Aucun patient", "Sélectionnez un patient d'abord")
            return

        self.image_viewer_visible = not self.image_viewer_visible

        if self.image_viewer_visible:
            self.viewer_panel.show()
            self.main_splitter.setSizes([self.width() // 2, self.width() // 2])
            self.show_current_page()
            self.toggle_btn.setText("Cacher visualisation")
        else:
            self.viewer_panel.hide()
            self.main_splitter.setSizes([self.width(), 0])
            self.toggle_btn.setText("Afficher visualisation")

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
                        item.setBackground(QColor(255, 200, 200))
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
