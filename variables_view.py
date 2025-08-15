import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QListWidget, QLineEdit,
    QPushButton, QHBoxLayout, QLabel, QMessageBox,
    QDialog, QComboBox, QFormLayout, QDialogButtonBox,
    QListWidgetItem
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
from ocr import detect_variables_from_image_folder
from main import CustomMessageBox


class VariableSelectionDialog(QDialog):
    def __init__(self, variables, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Variables to Add")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #333333;
                font-family: "Segoe UI";
                font-size: 11pt;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                color: #333333;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
            QListWidget::item:checked {
                color: #1a73e8;
            }
            QPushButton {
                background-color: #1a73e8;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #287ae6;
            }
        """)

        self.layout = QVBoxLayout(self)

        controls_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        deselect_all_btn = QPushButton("Deselect All")
        controls_layout.addWidget(select_all_btn)
        controls_layout.addWidget(deselect_all_btn)
        controls_layout.addStretch()
        self.layout.addLayout(controls_layout)

        self.list_widget = QListWidget()
        for var in variables:
            item = QListWidgetItem(var)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)
        self.layout.addWidget(self.list_widget)

        select_all_btn.clicked.connect(self.select_all)
        deselect_all_btn.clicked.connect(self.deselect_all)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def select_all(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Checked)

    def deselect_all(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Unchecked)

    def get_selected_variables(self):
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected


    def update_options_visibility(self):
        is_group = self.type_combo.currentIndex() == 1
        self.options_input.setVisible(is_group)
        self.layout.labelForField(self.options_input).setVisible(is_group)

    def get_data(self):
        name = self.name_input.text().strip()
        if not name:
            return None

        var_type = 'group' if self.type_combo.currentIndex() == 1 else 'text'
        options = []
        if var_type == 'group':
            options = [opt.strip() for opt in self.options_input.text().split(',') if opt.strip()]
            if not options:
                # A group must have options
                return None

        return {"name": name, "type": var_type, "options": options}


class VariablesView(QWidget):
    def __init__(self, project_data, save_callback, extract_callback):
        super().__init__()
        self.project_data = project_data
        self.save_callback = save_callback
        self.extract_callback = extract_callback
        self.initUI()

    # variables_view.py (modifications dans initUI)
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        title = QLabel("Définition des Variables")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #333333; padding-bottom: 5px;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                padding: 10px;
                font-size: 11pt;
                color: #333333;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-radius: 4px;
                margin-bottom: 5px;
                color: #333333;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
            QListWidget::item:selected {
                background-color: #e8f0fe;
                color: #1967d2;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.list_widget)

        # Buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        self.detect_btn = QPushButton("Auto-détection")
        self.detect_btn.clicked.connect(self.auto_detect_variables)
        self.detect_btn.setStyleSheet("""
            background-color: #28a745;
            color: white;
            min-width: 120px;
        """)

        self.extract_btn = QPushButton("Lancer l'extraction")
        self.extract_btn.clicked.connect(self.extract_callback)
        self.extract_btn.setStyleSheet("""
            background-color: #1a73e8;
            color: white;
            min-width: 120px;
        """)

        buttons_layout.addWidget(self.detect_btn)
        buttons_layout.addWidget(self.extract_btn)
        buttons_layout.addStretch()

        self.add_btn = QPushButton("Ajouter")
        self.edit_btn = QPushButton("Modifier")
        self.remove_btn = QPushButton("Supprimer")

        self.add_btn.clicked.connect(self.add_variable)
        self.edit_btn.clicked.connect(self.edit_variable)
        self.remove_btn.clicked.connect(self.remove_variable)

        self.add_btn.setStyleSheet("""
            background-color: #1a73e8;
            color: white;
            min-width: 80px;
        """)
        self.edit_btn.setStyleSheet("""
            background-color: #f1f3f4;
            color: #3c4043;
            border: 1px solid #dcdcdc;
            min-width: 80px;
        """)
        self.remove_btn.setStyleSheet("""
            background-color: #fce8e6;
            color: #c5221f;
            border: 1px solid #f9aba8;
            min-width: 80px;
        """)

        buttons_layout.addWidget(self.add_btn)
        buttons_layout.addWidget(self.edit_btn)
        buttons_layout.addWidget(self.remove_btn)

        layout.addLayout(buttons_layout)

        self.load_variables()

    def load_variables(self):
        self.list_widget.clear()
        if self.project_data and 'variables' in self.project_data:
            # Ensure project_data['variables'] is a list of dicts for backward compatibility
            if self.project_data['variables'] and isinstance(self.project_data['variables'][0], str):
                self.project_data['variables'] = [{"name": v, "type": "text", "options": []} for v in
                                                  self.project_data['variables']]

            for var in self.project_data.get('variables', []):
                if isinstance(var, dict):
                    item = QListWidgetItem(var.get('name', 'Variable sans nom'))
                    self.list_widget.addItem(item)

    def add_variable(self):
        dialog = VariableEditDialog(self)
        if dialog.exec_():
            data = dialog.get_data()
            if not data:
                CustomMessageBox.warning(self, "Invalide",
                                    "Le nom de la variable ne peut pas être vide, et un groupe doit avoir des options.")
                return

            # Check for duplicates
            existing_names = [v['name'] for v in self.project_data.get('variables', [])]
            if data['name'] in existing_names:
                CustomMessageBox.warning(self, "Dupliqué", f"La variable '{data['name']}' existe déjà.")
                return

            if 'variables' not in self.project_data:
                self.project_data['variables'] = []

            self.project_data['variables'].append(data)
            self.list_widget.addItem(data['name'])
            self.save_callback()

    def edit_variable(self):
        selected = self.list_widget.currentItem()
        if not selected:
            msg = CustomMessageBox(self)
            msg.setWindowTitle("Aucune sélection")
            msg.setText("Veuillez sélectionner une variable à modifier.")
            msg.setIcon(CustomMessageBox.Warning)
            msg.exec_()
            return

        row = self.list_widget.row(selected)
        current_var = self.project_data['variables'][row]

        dialog = VariableEditDialog(self, variable=current_var)
        if dialog.exec_():
            data = dialog.get_data()
            if not data:
                msg = CustomMessageBox(self)
                msg.setWindowTitle("Invalide")
                msg.setText("Le nom de la variable ne peut pas être vide, et un groupe doit avoir des options.")
                msg.setIcon(CustomMessageBox.Warning)
                msg.exec_()
                return

            # Check for duplicates if name changed
            if data['name'] != current_var['name']:
                existing_names = [v['name'] for i, v in enumerate(self.project_data['variables']) if i != row]
                if data['name'] in existing_names:
                    msg = CustomMessageBox(self)
                    msg.setWindowTitle("Dupliqué")
                    msg.setText(f"La variable '{data['name']}' existe déjà.")
                    msg.setIcon(CustomMessageBox.Warning)
                    msg.exec_()
                    return

            self.project_data['variables'][row] = data
            selected.setText(data['name'])
            self.save_callback()

    def remove_variable(self):
        selected = self.list_widget.currentItem()
        if not selected:
            CustomMessageBox.warning(self, "Aucune sélection", "Veuillez sélectionner une variable à supprimer.")
            return

        reply = CustomMessageBox.question(self, 'Confirmer la suppression',
                                     f'Êtes-vous sûr de vouloir supprimer la variable "{selected.text()}"?',
                                     CustomMessageBox.Yes | CustomMessageBox.No, CustomMessageBox.No)

        if reply == CustomMessageBox.Yes:
            row = self.list_widget.row(selected)
            del self.project_data['variables'][row]
            self.list_widget.takeItem(row)
            self.save_callback()

    def auto_detect_variables(self):
        # The source for variable detection should be a sample patient folder, not the main scan folder.
        # We use the first patient folder as a representative sample.
        patient_questionnaires = self.project_data.get('compiled_questionnaires')
        if not patient_questionnaires:
            CustomMessageBox.warning(self, "Dossiers patient manquants",
                                "Veuillez d'abord importer et organiser les scans (via le menu Outils) avant de lancer la détection.")
            return

        # Use the first patient's directory as the sample for detection
        sample_patient_dir = patient_questionnaires[0].get('patient_dir')
        if not sample_patient_dir or not os.path.exists(sample_patient_dir):
             CustomMessageBox.warning(self, "Dossier patient non trouvé",
                                f"Le dossier pour le premier patient ('{sample_patient_dir}') est introuvable. Veuillez réimporter les scans.")
             return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            # Call detection on the specific sample patient directory
            result = detect_variables_from_image_folder(sample_patient_dir)
        finally:
            QApplication.restoreOverrideCursor()

        if result.get("errors"):
            CustomMessageBox.critical(self, "Erreur de Détection", "\n".join(result["errors"]))
            return

        if not result.get("variables"):
            CustomMessageBox.information(self, "Aucune Variable Trouvée",
                                    "Aucune variable n'a pu être détectée dans les documents.")
            return

        existing_vars = {v['name'] for v in self.project_data.get('variables', [])}
        new_vars = [v for v in result["variables"] if v not in existing_vars]

        if not new_vars:
            CustomMessageBox.information(self, "Aucune Nouvelle Variable",
                                    "L'auto-détection n'a trouvé aucune variable qui ne soit pas déjà dans votre liste.")
            return

        dialog = VariableSelectionDialog(new_vars, self)
        if dialog.exec_():
            selected_vars = dialog.get_selected_variables()
            if selected_vars:
                for var_name in selected_vars:
                    new_var_data = {"name": var_name, "type": "text", "options": []}
                    self.project_data['variables'].append(new_var_data)
                    self.list_widget.addItem(var_name)
                self.save_callback()

    def update_view(self, project_data):
        self.project_data = project_data
        self.load_variables()
