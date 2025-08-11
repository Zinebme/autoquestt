from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QLineEdit,
    QPushButton, QHBoxLayout, QLabel, QMessageBox,
    QInputDialog, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class VariablesView(QWidget):
    def __init__(self, project_data, save_callback, extract_callback):
        super().__init__()
        self.project_data = project_data
        self.save_callback = save_callback
        self.extract_callback = extract_callback
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        title = QLabel("Define Variables to Extract:")
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
        font = QFont()
        font.setPointSize(11)  # Increased from default
        self.setFont(font)

        # List widget for variables
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
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
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.list_widget)

        # Input area
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        self.variable_input = QLineEdit()
        self.variable_input.setPlaceholderText("Enter variable name")
        self.variable_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        self.variable_input.returnPressed.connect(self.add_variable)

        self.add_btn = QPushButton("Add")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.add_btn.clicked.connect(self.add_variable)

        input_layout.addWidget(self.variable_input, 4)
        input_layout.addWidget(self.add_btn, 1)
        layout.addLayout(input_layout)

        # Control buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.edit_btn = QPushButton("Edit")
        self.remove_btn = QPushButton("Remove")
        self.extract_btn = QPushButton("Extract Data")

        for btn in [self.edit_btn, self.remove_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #ddd;
                    padding: 8px 15px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)

        self.extract_btn.setStyleSheet("""
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

        self.edit_btn.clicked.connect(self.edit_variable)
        self.remove_btn.clicked.connect(self.remove_variable)
        self.extract_btn.clicked.connect(self.extract_callback)

        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.extract_btn)
        layout.addLayout(btn_layout)

        self.load_variables()

    def load_variables(self):
        self.list_widget.clear()
        if self.project_data and 'variables' in self.project_data:
            for var in self.project_data['variables']:
                if isinstance(var, dict) and 'name' in var:
                    self.list_widget.addItem(var['name'])
                elif isinstance(var, str):
                    self.list_widget.addItem(var)

    def add_variable(self):
        variable_name = self.variable_input.text().strip()
        if not variable_name:
            return

        # Check for duplicates
        existing_vars = []
        for i in range(self.list_widget.count()):
            existing_vars.append(self.list_widget.item(i).text())

        if variable_name in existing_vars:
            QMessageBox.warning(self, "Duplicate", f"Variable '{variable_name}' already exists.")
            return

        # Add to project data
        if 'variables' not in self.project_data:
            self.project_data['variables'] = []

        # Use consistent format (all dicts or all strings)
        if len(self.project_data['variables']) > 0 and isinstance(self.project_data['variables'][0], dict):
            new_var = {"name": variable_name}
        else:
            new_var = variable_name

        self.project_data['variables'].append(new_var)

        # Add to list widget
        self.list_widget.addItem(variable_name)
        self.variable_input.clear()

        # Save changes
        self.save_callback()

    def edit_variable(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a variable to edit")
            return

        item = selected_items[0]
        old_name = item.text()
        new_name, ok = QInputDialog.getText(self, "Edit Variable",
                                            "Enter new variable name:",
                                            text=old_name)
        if not ok or not new_name.strip() or new_name == old_name:
            return

        # Update in project data
        for i, var in enumerate(self.project_data['variables']):
            if (isinstance(var, dict) and var.get('name') == old_name) or var == old_name:
                if isinstance(var, dict):
                    self.project_data['variables'][i]['name'] = new_name
                else:
                    self.project_data['variables'][i] = new_name
                break

        # Update in list widget
        item.setText(new_name)
        self.save_callback()

    def remove_variable(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a variable to remove")
            return

        item = selected_items[0]
        name = item.text()

        reply = QMessageBox.question(self, 'Confirm Removal',
                                     f'Are you sure you want to remove "{name}"?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # Remove from project data
            self.project_data['variables'] = [
                v for v in self.project_data['variables']
                if (v.get("name") if isinstance(v, dict) else v) != name
            ]

            # Remove from list widget
            self.list_widget.takeItem(self.list_widget.row(item))
            self.save_callback()

    def update_view(self, project_data):
        self.project_data = project_data
        self.load_variables()