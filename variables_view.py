import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QLineEdit,
    QPushButton, QHBoxLayout, QLabel, QMessageBox,
    QDialog, QComboBox, QFormLayout, QDialogButtonBox,
    QListWidgetItem, QCheckBox, QTextEdit, QScrollArea,
    QFrame, QSplitter, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
import os
import tempfile
import base64
from ocr import extract_data_from_image_folder, merge_images_vertically, preprocess_image, call_vision_model_for_json


class DraggableListWidget(QListWidget):
    """Custom QListWidget that supports drag and drop reordering"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)


class VariableEditDialog(QDialog):
    """Dialog to add or edit a variable with its type and options."""

    def __init__(self, parent=None, variable=None):
        super().__init__(parent)
        self.setWindowTitle("Éditer la Variable")
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QLineEdit, QComboBox {
                padding: 8px;
                border: 2px solid #e9ecef;
                border-radius: 6px;
                background-color: white;
                font-size: 11px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #4dabf7;
                outline: none;
            }
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-size: 11px;
            }
        """)

        self.layout = QFormLayout(self)
        self.layout.setSpacing(15)

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
                return None

        return {"name": name, "type": var_type, "options": options}


class AutoDetectDialog(QDialog):
    """Dialog for auto-detecting variables from the first patient"""
    
    def __init__(self, parent=None, project_data=None):
        super().__init__(parent)
        self.project_data = project_data
        self.detected_variables = []
        self.setWindowTitle("Détection Automatique des Variables")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #495057;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QCheckBox {
                font-size: 11px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #adb5bd;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #28a745;
                border-radius: 3px;
                background-color: #28a745;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-size: 11px;
                min-width: 100px;
            }
            QPushButton:hover {
                transform: translateY(-1px);
            }
        """)
        
        self.initUI()
        self.detect_variables()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Title
        title = QLabel("Variables détectées automatiquement")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #495057; margin-bottom: 10px;")
        layout.addWidget(title)

        # Status label
        self.status_label = QLabel("Analyse en cours...")
        self.status_label.setStyleSheet("color: #6c757d; font-style: italic;")
        layout.addWidget(self.status_label)

        # Variables group
        variables_group = QGroupBox("Variables trouvées")
        variables_layout = QVBoxLayout(variables_group)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Tout sélectionner")
        self.select_all_btn.setStyleSheet("background-color: #28a745; color: white;")
        self.select_all_btn.clicked.connect(self.select_all)
        
        self.deselect_all_btn = QPushButton("Tout désélectionner")
        self.deselect_all_btn.setStyleSheet("background-color: #6c757d; color: white;")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        
        controls_layout.addWidget(self.select_all_btn)
        controls_layout.addWidget(self.deselect_all_btn)
        controls_layout.addStretch()
        variables_layout.addLayout(controls_layout)

        # Scroll area for variables
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: white; border-radius: 6px;")
        
        self.variables_widget = QWidget()
        self.variables_layout = QVBoxLayout(self.variables_widget)
        scroll.setWidget(self.variables_widget)
        variables_layout.addWidget(scroll)
        
        layout.addWidget(variables_group)

        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.setStyleSheet("background-color: #6c757d; color: white;")
        cancel_btn.clicked.connect(self.reject)
        
        self.ok_btn = QPushButton("Ajouter les variables sélectionnées")
        self.ok_btn.setStyleSheet("background-color: #007bff; color: white;")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.ok_btn)
        layout.addLayout(button_layout)

    def detect_variables(self):
        """Detect variables from the first patient"""
        try:
            if not self.project_data.get('compiled_questionnaires'):
                self.status_label.setText("Aucun patient trouvé pour la détection")
                return

            first_patient = self.project_data['compiled_questionnaires'][0]
            patient_dir = first_patient['patient_dir']
            
            self.status_label.setText("Analyse des images du premier patient...")
            
            # Get images from first patient
            images = sorted([f for f in os.listdir(patient_dir) 
                           if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
            
            if not images:
                self.status_label.setText("Aucune image trouvée")
                return

            # Merge images and prepare for analysis
            full_image_paths = [os.path.join(patient_dir, img) for img in images]
            merged_path = os.path.join(tempfile.gettempdir(), "detection_merged.png")
            merge_images_vertically(full_image_paths, merged_path)
            
            # Preprocess image
            image_data = preprocess_image(merged_path)
            if not image_data:
                self.status_label.setText("Erreur lors du traitement de l'image")
                return

            encoded_image = base64.b64encode(image_data).decode("utf-8")
            
            # Call vision model for variable detection
            detection_prompt = """Analyse ce formulaire médical et identifie TOUTES les variables/champs de données présents.
            
Pour chaque variable trouvée, retourne UNIQUEMENT le nom de la variable (pas la valeur).
Retourne les variables dans l'ordre d'apparition de haut en bas dans le document.

Format de réponse: retourne un objet JSON avec une clé "variables" contenant une liste des noms de variables:
{
  "variables": ["nom_variable1", "nom_variable2", "nom_variable3", ...]
}

Ne retourne RIEN d'autre que l'objet JSON."""

            payload = {
                "prompt": detection_prompt,
                "image_base64": encoded_image,
                "max_tokens": 2048,
                "temperature": 0.0,
            }
            
            import requests
            response = requests.post("https://tpojbsbaej220w-8000.proxy.runpod.net/generate", 
                                   json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            text = data.get("text") or data.get("output", "")
            
            # Parse response
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                self.detected_variables = result.get("variables", [])
                self.display_variables()
            else:
                self.status_label.setText("Erreur lors de l'analyse des variables")
                
        except Exception as e:
            self.status_label.setText(f"Erreur: {str(e)}")

    def display_variables(self):
        """Display detected variables with checkboxes"""
        if not self.detected_variables:
            self.status_label.setText("Aucune variable détectée")
            return
            
        self.status_label.setText(f"{len(self.detected_variables)} variables détectées")
        
        # Clear existing widgets
        for i in reversed(range(self.variables_layout.count())):
            self.variables_layout.itemAt(i).widget().setParent(None)
        
        self.checkboxes = []
        for var_name in self.detected_variables:
            checkbox = QCheckBox(var_name)
            checkbox.setChecked(True)  # Default to selected
            checkbox.stateChanged.connect(self.update_ok_button)
            self.checkboxes.append(checkbox)
            self.variables_layout.addWidget(checkbox)
        
        self.variables_layout.addStretch()
        self.update_ok_button()

    def select_all(self):
        for checkbox in self.checkboxes:
            checkbox.setChecked(True)

    def deselect_all(self):
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)

    def update_ok_button(self):
        has_selection = any(cb.isChecked() for cb in self.checkboxes)
        self.ok_btn.setEnabled(has_selection)

    def get_selected_variables(self):
        """Return list of selected variable names"""
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]


class VariablesView(QWidget):
    def __init__(self, project_data, save_callback, extract_callback):
        super().__init__()
        self.project_data = project_data
        self.save_callback = save_callback
        self.extract_callback = extract_callback
        self.initUI()

    def initUI(self):
        # Apply modern styling
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #495057;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                padding: 10px 16px;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-size: 11px;
                min-width: 120px;
            }
            QPushButton:hover {
                transform: translateY(-1px);
            }
            QPushButton:pressed {
                transform: translateY(0px);
            }
            QListWidget {
                background-color: white;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 8px;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f1f3f4;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QLineEdit, QTextEdit {
                padding: 10px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
                font-size: 11px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #4dabf7;
                outline: none;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Gestion des Variables")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #495057; margin-bottom: 10px;")
        main_layout.addWidget(title)

        # Create splitter for two-column layout
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Variable Management
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        
        # Auto-detect group
        auto_group = QGroupBox("Détection Automatique")
        auto_layout = QVBoxLayout(auto_group)
        
        auto_desc = QLabel("Analyser automatiquement le premier patient pour détecter les variables")
        auto_desc.setStyleSheet("color: #6c757d; font-size: 10px; margin-bottom: 10px;")
        auto_desc.setWordWrap(True)
        auto_layout.addWidget(auto_desc)
        
        self.auto_detect_btn = QPushButton("🔍 Détecter les Variables")
        self.auto_detect_btn.setStyleSheet("background-color: #28a745; color: white;")
        self.auto_detect_btn.clicked.connect(self.auto_detect_variables)
        auto_layout.addWidget(self.auto_detect_btn)
        
        left_layout.addWidget(auto_group)

        # Manual entry group
        manual_group = QGroupBox("Saisie Manuelle")
        manual_layout = QVBoxLayout(manual_group)
        
        manual_desc = QLabel("Entrez les noms des variables séparés par des virgules")
        manual_desc.setStyleSheet("color: #6c757d; font-size: 10px; margin-bottom: 10px;")
        manual_layout.addWidget(manual_desc)
        
        self.manual_input = QTextEdit()
        self.manual_input.setMaximumHeight(80)
        self.manual_input.setPlaceholderText("Ex: nom_patient, age, diagnostic, traitement...")
        manual_layout.addWidget(self.manual_input)
        
        self.add_manual_btn = QPushButton("➕ Ajouter Variables")
        self.add_manual_btn.setStyleSheet("background-color: #007bff; color: white;")
        self.add_manual_btn.clicked.connect(self.add_manual_variables)
        manual_layout.addWidget(self.add_manual_btn)
        
        left_layout.addWidget(manual_group)
        
        # Individual variable management
        individual_group = QGroupBox("Variable Individuelle")
        individual_layout = QVBoxLayout(individual_group)
        
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ Ajouter")
        self.add_btn.setStyleSheet("background-color: #17a2b8; color: white;")
        self.edit_btn = QPushButton("✏️ Modifier")
        self.edit_btn.setStyleSheet("background-color: #ffc107; color: #212529;")
        
        self.add_btn.clicked.connect(self.add_variable)
        self.edit_btn.clicked.connect(self.edit_variable)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        individual_layout.addLayout(btn_layout)
        
        left_layout.addWidget(individual_group)
        left_layout.addStretch()

        # Right panel - Variables List
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        
        variables_group = QGroupBox("Variables Définies")
        variables_layout = QVBoxLayout(variables_group)
        
        list_controls = QHBoxLayout()
        list_info = QLabel("Glissez-déposez pour réorganiser")
        list_info.setStyleSheet("color: #6c757d; font-size: 10px; font-style: italic;")
        list_controls.addWidget(list_info)
        list_controls.addStretch()
        
        self.remove_btn = QPushButton("🗑️ Supprimer")
        self.remove_btn.setStyleSheet("background-color: #dc3545; color: white;")
        self.remove_btn.clicked.connect(self.remove_variable)
        list_controls.addWidget(self.remove_btn)
        
        variables_layout.addLayout(list_controls)

        # Draggable list widget
        self.list_widget = DraggableListWidget()
        self.list_widget.itemChanged.connect(self.on_item_changed)
        self.list_widget.model().rowsMoved.connect(self.on_rows_moved)
        variables_layout.addWidget(self.list_widget)
        
        right_layout.addWidget(variables_group)

        # Extract button
        self.extract_btn = QPushButton("🚀 Lancer l'Extraction des Données")
        self.extract_btn.setStyleSheet("""
            background-color: #6f42c1; 
            color: white; 
            font-size: 12px; 
            font-weight: bold; 
            padding: 15px;
            margin-top: 20px;
        """)
        self.extract_btn.clicked.connect(self.extract_callback)
        right_layout.addWidget(self.extract_btn)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 400])
        
        main_layout.addWidget(splitter)
        self.load_variables()

    def auto_detect_variables(self):
        """Open auto-detection dialog"""
        if not self.project_data.get('compiled_questionnaires'):
            QMessageBox.warning(self, "Aucun Patient", 
                              "Veuillez d'abord importer des questionnaires pour la détection automatique.")
            return
            
        dialog = AutoDetectDialog(self, self.project_data)
        if dialog.exec_():
            selected_vars = dialog.get_selected_variables()
            if selected_vars:
                # Convert to proper format and add to existing variables
                if 'variables' not in self.project_data:
                    self.project_data['variables'] = []
                
                existing_names = [v['name'] if isinstance(v, dict) else v 
                                for v in self.project_data['variables']]
                
                added_count = 0
                for var_name in selected_vars:
                    if var_name not in existing_names:
                        self.project_data['variables'].append({
                            "name": var_name,
                            "type": "text",
                            "options": []
                        })
                        added_count += 1
                
                if added_count > 0:
                    self.load_variables()
                    self.save_callback()
                    QMessageBox.information(self, "Variables Ajoutées", 
                                          f"{added_count} nouvelles variables ont été ajoutées.")
                else:
                    QMessageBox.information(self, "Aucune Nouvelle Variable", 
                                          "Toutes les variables détectées existent déjà.")

    def add_manual_variables(self):
        """Add variables from manual text input"""
        text = self.manual_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Saisie Vide", "Veuillez entrer au moins un nom de variable.")
            return
        
        # Parse comma-separated variables
        var_names = [name.strip() for name in text.split(',') if name.strip()]
        
        if not var_names:
            QMessageBox.warning(self, "Aucune Variable Valide", "Aucune variable valide trouvée.")
            return
        
        if 'variables' not in self.project_data:
            self.project_data['variables'] = []
        
        existing_names = [v['name'] if isinstance(v, dict) else v 
                         for v in self.project_data['variables']]
        
        added_count = 0
        for var_name in var_names:
            if var_name not in existing_names:
                self.project_data['variables'].append({
                    "name": var_name,
                    "type": "text", 
                    "options": []
                })
                added_count += 1
        
        if added_count > 0:
            self.load_variables()
            self.save_callback()
            self.manual_input.clear()
            QMessageBox.information(self, "Variables Ajoutées", 
                                  f"{added_count} variables ont été ajoutées.")
        else:
            QMessageBox.information(self, "Variables Existantes", 
                                  "Toutes les variables saisies existent déjà.")

    def load_variables(self):
        self.list_widget.clear()
        if self.project_data and 'variables' in self.project_data:
            # Ensure backward compatibility
            if self.project_data['variables'] and isinstance(self.project_data['variables'][0], str):
                self.project_data['variables'] = [{"name": v, "type": "text", "options": []} 
                                                 for v in self.project_data['variables']]

            for var in self.project_data.get('variables', []):
                if isinstance(var, dict):
                    item = QListWidgetItem(var.get('name', 'Variable sans nom'))
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                    self.list_widget.addItem(item)

    def on_item_changed(self, item):
        """Handle inline editing of variable names"""
        row = self.list_widget.row(item)
        new_name = item.text().strip()
        
        if not new_name:
            QMessageBox.warning(self, "Nom Invalide", "Le nom de la variable ne peut pas être vide.")
            self.load_variables()  # Reload to revert changes
            return
        
        # Check for duplicates
        existing_names = [v['name'] for i, v in enumerate(self.project_data['variables']) if i != row]
        if new_name in existing_names:
            QMessageBox.warning(self, "Nom Dupliqué", f"La variable '{new_name}' existe déjà.")
            self.load_variables()  # Reload to revert changes
            return
        
        # Update the variable name
        self.project_data['variables'][row]['name'] = new_name
        self.save_callback()

    def on_rows_moved(self, parent, start, end, destination, row):
        """Handle drag and drop reordering"""
        # Update the internal variables list to match the new order
        variables = self.project_data.get('variables', [])
        if start < len(variables) and row <= len(variables):
            # Calculate the actual destination index
            if row > start:
                dest_index = row - 1
            else:
                dest_index = row
            
            # Move the variable in the list
            moved_var = variables.pop(start)
            variables.insert(dest_index, moved_var)
            
            self.save_callback()

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
            self.load_variables()
            self.save_callback()

    def edit_variable(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "Aucune Sélection", "Veuillez sélectionner une variable à modifier.")
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
            self.load_variables()
            self.save_callback()

    def remove_variable(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "Aucune Sélection", "Veuillez sélectionner une variable à supprimer.")
            return

        reply = QMessageBox.question(self, 'Confirmer la Suppression',
                                   f'Êtes-vous sûr de vouloir supprimer la variable "{selected.text()}"?',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            row = self.list_widget.row(selected)
            del self.project_data['variables'][row]
            self.load_variables()
            self.save_callback()

    def update_view(self, project_data):
        self.project_data = project_data
        self.load_variables()