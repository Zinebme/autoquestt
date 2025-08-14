from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QVBoxLayout, QPushButton, QScrollArea,
    QSplitter, QFrame, QSizePolicy, QMessageBox
)
from PyQt5.QtGui import QPixmap, QColor, QFont, QPalette
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
        # Apply modern styling
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
            QPushButton {
                padding: 10px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-size: 11px;
                min-width: 100px;
            }
            QPushButton:hover {
                transform: translateY(-1px);
            }
            QTableWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                gridline-color: #f1f3f4;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 10px;
                border: 1px solid #dee2e6;
                font-weight: bold;
                color: #495057;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f1f3f4;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QScrollArea {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                background-color: #f8f9fa;
            }
            QLabel {
                color: #495057;
            }
        """)
        
        # Main splitter for resizable panels
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setStyleSheet("QSplitter::handle { background: #dee2e6; width: 2px; }")

        # Left panel - Table
        self.table_panel = QFrame()
        table_layout = QVBoxLayout(self.table_panel)
        table_layout.setContentsMargins(15, 15, 15, 15)
        table_layout.setSpacing(15)

        # Title
        title = QLabel("Vérification des Données Extraites")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #495057; margin-bottom: 10px;")
        table_layout.addWidget(title)

        # Control button
        self.toggle_btn = QPushButton("📋 Afficher la Visualisation")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_viewer)
        table_layout.addWidget(self.toggle_btn)

        # Data table
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.AllEditTriggers)
        table_layout.addWidget(self.table)

        # Right panel - Image Viewer
        self.viewer_panel = QFrame()
        viewer_layout = QVBoxLayout(self.viewer_panel)
        viewer_layout.setContentsMargins(15, 15, 15, 15)
        viewer_layout.setSpacing(15)

        # Viewer title
        viewer_title = QLabel("Visualisation des Documents")
        viewer_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        viewer_title.setStyleSheet("color: #495057;")
        viewer_layout.addWidget(viewer_title)

        # Viewer controls
        controls = QHBoxLayout()
        controls.setSpacing(15)

        self.prev_btn = QPushButton("◀ Précédent")
        self.next_btn = QPushButton("Suivant ▶")
        self.page_label = QLabel("Page: -/-")
        self.zoom_in_btn = QPushButton("🔍 Zoom +")
        self.zoom_out_btn = QPushButton("🔍 Zoom -")

        for btn in [self.prev_btn, self.next_btn, self.zoom_in_btn, self.zoom_out_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #545b62;
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
        self.scroll_area.setWidgetResizable(True)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: white; border: 1px solid #dee2e6;")
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

    def toggle_viewer(self):
        """Toggle image viewer visibility"""
        if not self.current_patient:
            QMessageBox.warning(self, "Aucun Patient", "Sélectionnez un patient d'abord")
            return

        self.image_viewer_visible = not self.image_viewer_visible

        if self.image_viewer_visible:
            self.viewer_panel.show()
            self.main_splitter.setSizes([self.width() // 2, self.width() // 2])
            self.show_current_page()
            self.toggle_btn.setText("📋 Cacher la Visualisation")
        else:
            self.viewer_panel.hide()
            self.main_splitter.setSizes([self.width(), 0])
            self.toggle_btn.setText("📋 Afficher la Visualisation")

    def load_data(self):
        self.table.blockSignals(True)
        try:
            self.table.clear()

            if not self.project_data.get('extracted_data'):
                return

            # Setup headers - maintain variable order from Variables View
            variable_names = []
            for v in self.project_data.get('variables', []):
                if isinstance(v, dict):
                    variable_names.append(v['name'])
                else:
                    variable_names.append(str(v))
            
            headers = ["Patient"] + variable_names + ["Erreurs"]
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)

            # Populate rows
            for row, (patient_id, data) in enumerate(self.project_data['extracted_data'].items()):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(patient_id))

                # Maintain variable order
                for col, var_name in enumerate(variable_names, start=1):
                    value = str(data["data"]["variables"].get(var_name, ""))
                    item = QTableWidgetItem(value)
                    
                    # Handle conflicts - show in red without "CONFLICT:" prefix
                    if value.startswith("CONFLICT:"):
                        conflict_values = value[9:]  # Remove "CONFLICT:" prefix
                        item.setText(conflict_values)
                        item.setForeground(QColor(220, 53, 69))  # Bootstrap danger red
                        item.setToolTip("Conflit détecté: plusieurs valeurs trouvées")
                    elif '?' in value:
                        item.setBackground(QColor(255, 243, 205))  # Light warning yellow
                        item.setToolTip("Valeur incertaine")
                    
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
            if column > 0 and column < self.table.columnCount() - 1:  # Not patient or errors column
                var_name = self.table.horizontalHeaderItem(column).text()
            else:
                return  # Don't save changes to patient ID or errors
                
            new_value = self.table.item(row, column).text()

            if patient_id in self.project_data['extracted_data']:
                self.project_data['extracted_data'][patient_id]["data"]["variables"][var_name] = new_value
                
                # Remove conflict formatting if user manually edits
                item = self.table.item(row, column)
                item.setForeground(QColor(0, 0, 0))  # Reset to black
                item.setToolTip("")  # Clear tooltip
                
                self.save_callback()
        except Exception as e:
            print(f"Error saving change: {e}")

    def update_view(self, project_data=None):
        """Refresh view with new data"""
        if project_data:
            self.project_data = project_data
        self.load_data()
