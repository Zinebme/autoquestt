from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QLineEdit,
    QPushButton, QHBoxLayout, QLabel, QMessageBox,
    QDialog, QComboBox, QFormLayout, QDialogButtonBox,
    QListWidgetItem
)
from PyQt5.QtCore import Qt


class VariableEditDialog(QDialog):
    """
    A custom dialog to add or edit a variable with its type and options.
    """

    def __init__(self, parent=None, variable=None):
        super().__init__(parent)
        self.setWindowTitle("Éditer la Variable")

        self.layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.type_combo = QComboBox()
        self.options_input = QLineEdit()

        self.type_combo.addItems(["Texte / Case unique", "Groupe de Choix Exclusifs"])

        self.layout.addRow("Nom de la variable:", self.name_input)
        self.layout.addRow("Type:", self.type_combo)
        self.layout.addRow("Options (séparées par virgule):", self.options_input)

        self.type_combo.currentIndexChanged.connect(self.update_options_visibility)

        # Set initial data if editing an existing variable
        if variable:
            self.name_input.setText(variable.get('name', ''))
            var_type = variable.get('type', 'text')
            if var_type == 'group':
                self.type_combo.setCurrentIndex(1)
                self.options_input.setText(", ".join(variable.get('options', [])))
            else:
                self.type_combo.setCurrentIndex(0)

        self.update_options_visibility()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.button_box)

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

    def initUI(self):
        layout = QVBoxLayout(self)
        title = QLabel("Définir les variables à extraire:")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Ajouter une variable")
        self.edit_btn = QPushButton("Modifier")
        self.remove_btn = QPushButton("Supprimer")

        self.add_btn.clicked.connect(self.add_variable)
        self.edit_btn.clicked.connect(self.edit_variable)
        self.remove_btn.clicked.connect(self.remove_variable)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.remove_btn)
        layout.addLayout(btn_layout)

        self.extract_btn = QPushButton("Lancer l'extraction des données")
        self.extract_btn.clicked.connect(self.extract_callback)
        layout.addWidget(self.extract_btn)

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
                QMessageBox.warning(self, "Invalide",
                                    "Le nom de la variable ne peut pas être vide, et un groupe doit avoir des options.")
                return

            # Check for duplicates
            existing_names = [v['name'] for v in self.project_data.get('variables', [])]
            if data['name'] in existing_names:
                QMessageBox.warning(self, "Dupliqué", f"La variable '{data['name']}' existe déjà.")
                return

            if 'variables' not in self.project_data:
                self.project_data['variables'] = []

            self.project_data['variables'].append(data)
            self.list_widget.addItem(data['name'])
            self.save_callback()

    def edit_variable(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "Aucune sélection", "Veuillez sélectionner une variable à modifier.")
            return

        row = self.list_widget.row(selected)
        current_var = self.project_data['variables'][row]

        dialog = VariableEditDialog(self, variable=current_var)
        if dialog.exec_():
            data = dialog.get_data()
            if not data:
                QMessageBox.warning(self, "Invalide",
                                    "Le nom de la variable ne peut pas être vide, et un groupe doit avoir des options.")
                return

            # Check for duplicates if name changed
            if data['name'] != current_var['name']:
                existing_names = [v['name'] for i, v in enumerate(self.project_data['variables']) if i != row]
                if data['name'] in existing_names:
                    QMessageBox.warning(self, "Dupliqué", f"La variable '{data['name']}' existe déjà.")
                    return

            self.project_data['variables'][row] = data
            selected.setText(data['name'])
            self.save_callback()

    def remove_variable(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "Aucune sélection", "Veuillez sélectionner une variable à supprimer.")
            return

        reply = QMessageBox.question(self, 'Confirmer la suppression',
                                     f'Êtes-vous sûr de vouloir supprimer la variable "{selected.text()}"?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            row = self.list_widget.row(selected)
            del self.project_data['variables'][row]
            self.list_widget.takeItem(row)
            self.save_callback()

    def update_view(self, project_data):
        self.project_data = project_data
        self.load_variables()
