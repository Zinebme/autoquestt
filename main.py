import sys
import os
import json
import gc
import psutil
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QAction, QToolBar, QStatusBar,
    QListWidget, QListWidgetItem, QStackedWidget,
    QLabel, QFileDialog, QMessageBox, QInputDialog,
    QProgressDialog, QSplitter, QPushButton
)
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox)
from PyQt5 import QtGui
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QSize, Qt, QTimer

# These imports are from the original script.
# As I don't have the files, I'll assume they exist and work as intended.
# If they don't, I'll need to ask the user for them.
try:
    from documents_view import DocumentsView
    from variables_view import VariablesView
    from verification_view import VerificationView
    from ocr import extract_data_from_image_folder, prepare_patient_folders
except ImportError:
    # If the view files are not found, create dummy classes to allow the app to run
    # This is for development and testing purposes without the full project structure.
    class DocumentsView(QWidget):
        def __init__(self, project_data):
            super().__init__()
            self.layout = QVBoxLayout(self)
            self.label = QLabel("Vue des Documents (Fichier manquant)")
            self.layout.addWidget(self.label)

        def update_view(self, project_data=None):
            pass


    class VariablesView(QWidget):
        def __init__(self, project_data, save_callback, extract_callback):
            super().__init__()
            self.layout = QVBoxLayout(self)
            self.label = QLabel("Vue des Variables (Fichier manquant)")
            self.layout.addWidget(self.label)

        def update_view(self, project_data=None):
            pass


    class VerificationView(QWidget):
        def __init__(self, project_data, save_callback):
            super().__init__()
            self.layout = QVBoxLayout(self)
            self.label = QLabel("Vue de Vérification (Fichier manquant)")
            self.layout.addWidget(self.label)

        def update_view(self, project_data=None):
            pass


    def extract_data_from_image_folder(path, vars):
        print(f"INFO: Appel factice de extract_data_from_image_folder pour {path}")
        return {"variables": {v['name']: "dummy_value" for v in vars}, "errors": []}


    def prepare_patient_folders(source, output, pages):
        print(f"INFO: Appel factice de prepare_patient_folders")
        # Create some dummy patient folders for testing
        patients = []
        for i in range(3):
            patient_id = f"Patient_{i + 1}"
            patient_dir = os.path.join(output, patient_id)
            os.makedirs(patient_dir, exist_ok=True)
            # Create a dummy image file
            with open(os.path.join(patient_dir, "page_1.png"), "w") as f:
                f.write("dummy image")
            patients.append({'patient_dir': patient_dir})
        return patients

class CustomMessageBox(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            CustomMessageBox {
                background-color: #ffffff;
            }
            QLabel {
                color: #333333;
                font-size: 11pt;
            }
            QPushButton {
                background-color: #1a73e8;
                color: white;
                min-width: 80px;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #287ae6;
            }
        """)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- Police de base ---
        self.base_font = QtGui.QFont("Segoe UI", 11)  # Police moderne et lisible
        self.setFont(self.base_font)

        # --- Style moderne ---
        self.apply_stylesheet()

        # --- Gestion de la mémoire ---
        self.memory_timer = QTimer()
        self.memory_timer.timeout.connect(self.check_memory)
        self.memory_timer.start(5000)

        # --- Données du projet ---
        self.project_path = None
        self.project_data = {
            'scans_source_dir': None,
            'extracted_data': {},
            'variables': [],
            'pages_per_questionnaire': 1,
            'compiled_questionnaires': []
        }

        self.setWindowTitle("AutoQuest")
        self.setGeometry(100, 100, 1280, 800)
        # TODO: Add app icon file
        # self.setWindowIcon(QtGui.QIcon("icons/app_icon.png"))

        self.save_project_data = self._save_project_data
        self.extract_data = self.safe_extract_data

        # --- Création de l'interface ---
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.create_sidebar()
        self.create_central_area()

        self.main_splitter.addWidget(self.sidebar)
        self.main_splitter.addWidget(self.central_widget)
        self.main_splitter.setSizes([220, 1060])
        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, False)

        self.setCentralWidget(self.main_splitter)

        self.create_menus()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Aucun projet chargé. Prêt.")

    # main.py (modifications dans apply_stylesheet)
    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
            QWidget {
                font-family: "Segoe UI", sans-serif;
                color: #333333; /* Couleur de texte par défaut */
            }
            QMenuBar {
                background-color: #ffffff;
                border-bottom: 1px solid #dcdcdc;
            }
            QMenuBar::item {
                padding: 8px 16px;
                background-color: transparent;
                color: #333333;
            }
            QMenuBar::item:selected {
                background-color: #e8f0fe;
                color: #1967d2;
            }
            QMenu {
                background-color: #ffffff;
                border: 1px solid #dcdcdc;
                padding: 8px;
                color: #333333;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
                color: #333333;
            }
            QMenu::item:selected {
                background-color: #e8f0fe;
                color: #1967d2;
            }
            QStatusBar {
                background: #ffffff;
                border-top: 1px solid #dcdcdc;
                color: #333333;
            }
            QSplitter::handle {
                background: #dcdcdc;
            }
            QSplitter::handle:horizontal {
                width: 1px;
            }
            QLabel {
                color: #212529;
                font-size: 11pt;
            }
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 11pt;
                border-radius: 4px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #287ae6;
            }
            QPushButton:pressed {
                background-color: #1b65c9;
            }
            QPushButton:disabled {
                background-color: #dcdcdc;
                color: #a0a0a0;
            }
            QDialog, CustomMessageBox, QProgressDialog, QInputDialog {
                background-color: #ffffff;
                font-family: "Segoe UI", sans-serif;
                font-size: 11pt;
                color: #333333;
            }
            CustomMessageBox {
                background-color: #ffffff;
            }
            CustomMessageBox QLabel {
                color: #333333;
            }
            QListWidget {
                background-color: #ffffff;
                color: #333333;
            }
            QTableWidget {
                background-color: #ffffff;
                color: #333333;
            }
        """)

    def check_memory(self):
        try:
            mem = psutil.virtual_memory()
            if mem.percent > 85:
                gc.collect()
                if mem.percent > 90:
                    self.statusBar().showMessage(f"Avertissement : Utilisation mémoire élevée ({mem.percent}%)", 3000)
        except Exception:
            pass

    def create_sidebar(self):
        self.sidebar = QListWidget()
        self.sidebar.setMinimumWidth(220)
        self.sidebar.setMaximumWidth(350)
        self.sidebar.setIconSize(QSize(22, 22))
        self.sidebar.setFont(QtGui.QFont("Segoe UI", 11))

        self.sidebar.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                color: #212529;
                border: none;
                outline: 0;
                border-right: 1px solid #dcdcdc;
            }
            QListWidget::item {
                padding: 16px 24px;
                border-bottom: 1px solid #f0f2f5;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
            QListWidget::item:selected {
                background-color: #e8f0fe;
                border-left: 3px solid #1967d2;
                color: #1967d2;
                font-weight: bold;
            }
            QToolTip {
                background-color: #333;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
        """)

        # TODO: Add icon files for sidebar items
        items = [
            ("Projet", "Gérer les détails du projet"),
            ("Documents", "Visualiser et organiser les documents"),
            ("Extraction", "Définir les variables et extraire les données"),
            ("Vérification", "Vérifier les données extraites"),
            ("Exportation", "Exporter les résultats finaux")
        ]

        for text, tooltip in items:
            item = QListWidgetItem(text)
            item.setToolTip(tooltip)
            self.sidebar.addItem(item)

        self.sidebar.currentRowChanged.connect(self.change_view)
        self.sidebar.setEnabled(False)

    def create_central_area(self):
        self.central_widget = QStackedWidget()
        self.central_widget.setStyleSheet("background-color: transparent; border: none;")

        # Vue Projet
        project_view = QWidget()
        project_layout = QVBoxLayout(project_view)
        project_layout.setAlignment(Qt.AlignCenter)
        self.project_label = QLabel("Aucun projet chargé")
        self.project_label.setFont(QtGui.QFont("Segoe UI", 16, QFont.Light))
        self.project_label.setStyleSheet("color: #6c757d;")
        project_layout.addWidget(self.project_label)
        self.central_widget.addWidget(project_view)

        # Vue Documents
        self.documents_view = DocumentsView(self.project_data)
        self.central_widget.addWidget(self.documents_view)

        # Vue Variables (Extraction)
        self.variables_view = VariablesView(self.project_data, self.save_project_data, self.extract_data)
        self.central_widget.addWidget(self.variables_view)

        # Vue Vérification
        self.verification_view = VerificationView(self.project_data, self.save_project_data)
        self.central_widget.addWidget(self.verification_view)

        # Vue Exportation
        export_view = QWidget()
        export_layout = QVBoxLayout(export_view)
        export_layout.setAlignment(Qt.AlignCenter)
        export_label = QLabel("Exportation des données")
        export_label.setFont(QtGui.QFont("Segoe UI", 16, QFont.Light))
        export_label.setStyleSheet("color: #6c757d;")
        export_layout.addWidget(export_label)
        self.central_widget.addWidget(export_view)

    def create_menus(self):
        menu_bar = self.menuBar()

        # Menu Fichier
        file_menu = menu_bar.addMenu("&Fichier")

        # TODO: Add icon files for menu actions
        new_project_action = QAction("&Nouveau Projet...", self)
        new_project_action.setShortcut("Ctrl+N")
        new_project_action.triggered.connect(self.safe_new_project)
        file_menu.addAction(new_project_action)

        open_project_action = QAction("&Ouvrir un Projet...", self)
        open_project_action.setShortcut("Ctrl+O")
        open_project_action.triggered.connect(self.safe_open_project)
        file_menu.addAction(open_project_action)

        self.save_action = QAction("&Enregistrer", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self._save_project_data)
        self.save_action.setEnabled(False)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()

        exit_action = QAction("&Quitter", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Menu Outils
        tools_menu = menu_bar.addMenu("&Outils")

        self.import_action = QAction("&Importer des Scans...", self)
        self.import_action.setShortcut("Ctrl+I")
        self.import_action.triggered.connect(self.safe_import_scans)
        self.import_action.setEnabled(False)
        tools_menu.addAction(self.import_action)


        tools_menu.addSeparator()

        self.extract_action = QAction("Lancer l'&extraction des données", self)
        self.extract_action.setShortcut("Ctrl+E")
        self.extract_action.triggered.connect(self.safe_extract_data)
        self.extract_action.setEnabled(False)
        tools_menu.addAction(self.extract_action)

        self.export_action = QAction("&Exporter vers Excel...", self)
        self.export_action.setShortcut("Ctrl+Shift+E")
        self.export_action.triggered.connect(self.safe_export_to_excel)
        self.export_action.setEnabled(False)
        tools_menu.addAction(self.export_action)

        help_menu = menu_bar.addMenu("&Aide")

        help_action = QAction("&Guide d'utilisation", self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)

    def show_help(self):
        """Affiche le guide d'utilisation dans une fenêtre redimensionnable"""
        try:
            help_text = """
            <style>
                h1 { color: #1a73e8; font-size: 18pt; }
                h2 { color: #1a73e8; font-size: 14pt; margin-top: 12px; }
                body { font-family: "Segoe UI"; font-size: 11pt; }
                ul { margin-left: 20px; }
                li { margin-bottom: 6px; }
            </style>
            <h1>Guide d'utilisation d'AutoQuest</h1>
            <h2>1. Création/Ouverture d'un projet</h2>
            <p><b>Nouveau Projet</b> : Créez un nouveau projet en spécifiant un dossier parent et un nom de projet.</p>
            <p><b>Ouvrir Projet</b> : Charge un projet existant à partir de son dossier.</p>

            <h2>2. Importation des scans</h2>
            <p>Utilisez <b>Outils > Importer des Scans</b> pour :</p>
            <ul>
                <li>Sélectionner le dossier contenant les images des questionnaires</li>
                <li>Spécifier le nombre de pages par questionnaire</li>
            </ul>
            <p>Les documents seront organisés en dossiers patients automatiquement.</p>

            <h2>3. Définition des variables</h2>
            <p>Dans l'onglet <b>Extraction</b> :</p>
            <ul>
                <li><b>Auto-détection</b> : L'application analyse un questionnaire pour suggérer des variables</li>
                <li><b>Ajouter/Modifier</b> : Définissez manuellement les variables à extraire</li>
                <li>Pour les cases à cocher, créez une variable de type "groupe" avec les options possibles</li>
            </ul>

            <h2>4. Extraction des données</h2>
            <p>Cliquez sur <b>Lancer l'extraction</b> pour :</p>
            <ul>
                <li>Extraire les valeurs pour toutes les variables définies</li>
                <li>Les résultats apparaissent dans l'onglet Vérification</li>
            </ul>

            <h2>5. Vérification et correction</h2>
            <p>Dans l'onglet <b>Vérification</b> :</p>
            <ul>
                <li>Visualisez les données extraites dans un tableau</li>
                <li>Cliquez sur un patient pour voir le document original</li>
                <li>Corrigez directement les valeurs si nécessaire</li>
                <li>Utilisez les boutons de zoom et navigation pour inspecter le document</li>
            </ul>

            <h2>6. Exportation des résultats</h2>
            <p>Utilisez <b>Outils > Exporter vers Excel</b> pour sauvegarder les données dans un fichier Excel.</p>

            <h2>Conseils</h2>
            <ul>
                <li>Sauvegardez régulièrement votre projet (Ctrl+S)</li>
                <li>Pour les documents multipages, vérifiez que toutes les pages sont bien importées</li>
                <li>Les variables avec valeurs douteuses sont marquées en orange</li>
            </ul>
            """

            help_dialog = QDialog(self)
            help_dialog.setWindowTitle("Aide - Guide d'utilisation")
            help_dialog.setWindowFlags(help_dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
            help_dialog.resize(900, 700)  # Taille initiale plus grande

            layout = QVBoxLayout(help_dialog)

            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setHtml(help_text)

            # Utilisez la même police que votre application
            font = QFont("Segoe UI", 11)  # Police et taille comme dans votre app
            text_edit.setFont(font)

            # Barre de défilement toujours visible
            text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

            # Bouton Fermer
            btn_fermer = QPushButton("Fermer")
            btn_fermer.clicked.connect(help_dialog.close)
            btn_fermer.setStyleSheet("""
                QPushButton {
                    background-color: #1a73e8;
                    color: white;
                    padding: 8px 16px;
                    min-width: 100px;
                }
            """)

            layout.addWidget(text_edit)
            layout.addWidget(btn_fermer, alignment=Qt.AlignCenter)

            help_dialog.exec_()

        except Exception as e:
            print(f"Erreur lors de l'affichage de l'aide: {str(e)}")
            QMessageBox.critical(self, "Erreur", f"Impossible d'afficher l'aide:\n{str(e)}")

    def change_view(self, index):
        self.central_widget.setCurrentIndex(index)
        # Update sidebar selection style
        self.sidebar.setCurrentRow(index)

    def safe_new_project(self):
        try:
            path = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier parent pour le projet",
                                                    os.path.expanduser("~"))
            if not path:
                return

            project_name, ok = QInputDialog.getText(self, "Nouveau Projet", "Entrez le nom du projet :")
            if not ok or not project_name.strip():
                return

            project_folder = os.path.join(path, project_name)
            os.makedirs(project_folder, exist_ok=True)

            os.makedirs(os.path.join(project_folder, "patients"), exist_ok=True)
            os.makedirs(os.path.join(project_folder, "exports"), exist_ok=True)

            project_data = {
                'scans_source_dir': None,
                'extracted_data': {},
                'variables': [],
                'pages_per_questionnaire': 1,
                'compiled_questionnaires': []
            }

            with open(os.path.join(project_folder, "project.json"), 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4)

            self.load_project(project_folder)
        except Exception as e:
            CustomMessageBox.critical(self, "Erreur", f"Erreur inattendue lors de la création du projet :\n{str(e)}")
        finally:
            gc.collect()

    def safe_open_project(self):
        try:
            path = QFileDialog.getExistingDirectory(self, "Ouvrir un projet", os.path.expanduser("~"))
            if path:
                project_file = os.path.join(path, "project.json")
                if os.path.exists(project_file):
                    self.load_project(path)
                else:
                    CustomMessageBox.warning(self, "Projet invalide",
                                        "Le dossier sélectionné ne contient pas de fichier 'project.json' valide.")
        except Exception as e:
            CustomMessageBox.critical(self, "Erreur", f"Échec de l'ouverture du projet :\n{str(e)}")
        finally:
            gc.collect()

    def load_project(self, path):
        try:
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                CustomMessageBox.warning(self, "Avertissement Mémoire",
                                    "La mémoire système est trop utilisée pour charger ce projet en toute sécurité.")
                return

            self.project_path = path
            self._load_project_data()
            self.setWindowTitle(f"AutoQuest - {os.path.basename(path)}")
            self.statusBar().showMessage(f"Projet chargé : {path}")

            self.sidebar.setEnabled(True)
            self.save_action.setEnabled(True)
            self.import_action.setEnabled(True)
            self.extract_action.setEnabled(True)
            self.export_action.setEnabled(True)

            self.project_label.setText(f"Dossier du projet : {os.path.basename(path)}")

            self.documents_view.update_view(self.project_data)
            self.variables_view.update_view(self.project_data)
            self.verification_view.update_view(self.project_data)

            self.sidebar.setCurrentRow(0)

        except Exception as e:
            CustomMessageBox.critical(self, "Erreur de chargement", f"Échec du chargement du projet :\n{str(e)}")
        finally:
            gc.collect()

    def _load_project_data(self):
        path = os.path.join(self.project_path, "project.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.project_data = json.load(f)

    def _save_project_data(self):
        if not self.project_path:
            return
        try:
            path = os.path.join(self.project_path, "project.json")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.project_data, f, indent=4)
            self.statusBar().showMessage("Projet enregistré avec succès.", 3000)
        except Exception as e:
            CustomMessageBox.critical(self, "Erreur de sauvegarde", f"Échec de la sauvegarde du projet :\n{str(e)}")

    def safe_import_scans(self):
        if not self.project_path:
            return

        try:
            source_dir = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier contenant les scans",
                                                          os.path.expanduser("~"))
            if not source_dir:
                return

            if not any(f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')) for f in os.listdir(source_dir)):
                CustomMessageBox.warning(self, "Aucune image", "Le dossier sélectionné ne contient aucune image supportée.")
                return

            pages_per_q, ok = QInputDialog.getInt(self, "Structure du questionnaire",
                                                  "Nombre de pages par questionnaire :", 1, 1, 100)
            if not ok:
                return

            progress = QProgressDialog("Organisation des scans...", "Annuler", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(0)
            QApplication.processEvents()

            self.project_data['scans_source_dir'] = source_dir
            self.project_data['pages_per_questionnaire'] = pages_per_q

            output_dir = os.path.join(self.project_path, "patients")
            progress.setValue(20)
            QApplication.processEvents()

            try:
                self.project_data['compiled_questionnaires'] = prepare_patient_folders(
                    source_dir, output_dir, pages_per_q)

                progress.setValue(80)
                self.documents_view.update_view(self.project_data)
                self._save_project_data()

                progress.setValue(100)
                CustomMessageBox.information(self, "Importation réussie",
                                        f"{len(self.project_data['compiled_questionnaires'])} dossiers patient ont été préparés.")
            except Exception as e:
                CustomMessageBox.critical(self, "Erreur durant l'importation", str(e))
            finally:
                progress.close()
                gc.collect()

        except Exception as e:
            CustomMessageBox.critical(self, "Erreur d'importation", f"Échec de l'importation des scans :\n{str(e)}")
        finally:
            gc.collect()

    def safe_extract_data(self):
        if not self.project_data.get("compiled_questionnaires"):
            CustomMessageBox.warning(self, "Données manquantes", "Veuillez d'abord importer et organiser les scans.")
            return

        variables = self.project_data.get("variables", [])
        if not variables:
            CustomMessageBox.warning(self, "Aucune variable définie",
                                "Veuillez définir des variables avant de lancer l'extraction.")
            return

        total_patients = len(self.project_data['compiled_questionnaires'])
        progress = QProgressDialog("Extraction des données en cours...", "Annuler", 0, total_patients, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(0)
        QApplication.processEvents()

        try:
            extracted_data = self.project_data.get("extracted_data", {})
            processed_count = 0
            error_count = 0

            for i, patient in enumerate(self.project_data['compiled_questionnaires']):
                if progress.wasCanceled():
                    break

                progress.setValue(i)
                patient_id = os.path.basename(patient['patient_dir'])
                progress.setLabelText(f"Traitement du patient : {patient_id}...")
                QApplication.processEvents()

                try:
                    patient_path = patient['patient_dir']
                    if not os.path.exists(patient_path):
                        raise FileNotFoundError(f"Dossier patient non trouvé : {patient_path}")

                    result = extract_data_from_image_folder(patient_path, variables)
                    extracted_data[patient_id] = {
                        "data": result,
                        "error": None
                    }
                    processed_count += 1

                except Exception as e:
                    error_count += 1
                    extracted_data[patient_id] = {
                        "data": {"variables": {}, "errors": [str(e)]},
                        "error": str(e)
                    }

                if i % 5 == 0:
                    gc.collect()

            self.project_data["extracted_data"] = extracted_data
            self._save_project_data()

            self.verification_view.update_view(self.project_data)

            progress.setValue(total_patients)
            CustomMessageBox.information(
                self,
                "Extraction terminée",
                f"Traitement terminé.\nPatients traités : {processed_count}\nPatients en erreur : {error_count}"
            )

        except Exception as e:
            CustomMessageBox.critical(self, "Erreur d'extraction",
                                 f"Une erreur fatale est survenue durant l'extraction :\n{str(e)}")
        finally:
            progress.close()
            gc.collect()

    def show_info(self, title, message):
        msg = CustomMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(CustomMessageBox.Information)
        msg.exec_()

    def show_warning(self, title, message):
        msg = CustomMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(CustomMessageBox.warning)
        msg.exec_()

    def show_error(self, title, message):
        msg = CustomMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(CustomMessageBox.Critical)
        msg.exec_()

    def safe_export_to_excel(self):
        if not self.project_path:
            return

        data_dict = self.project_data.get('extracted_data', {})
        if not data_dict:
            CustomMessageBox.warning(self, "Aucune donnée", "Aucune donnée extraite à exporter.")
            return

        default_path = os.path.join(self.project_path, "exports", "donnees_extraites.xlsx")
        excel_path, _ = QFileDialog.getSaveFileName(self, "Exporter vers Excel", default_path,
                                                    "Fichiers Excel (*.xlsx)")

        if not excel_path:
            return

        try:
            progress = QProgressDialog("Exportation vers Excel...", "Annuler", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(10)
            QApplication.processEvents()

            rows = []
            for patient_id, result in data_dict.items():
                if progress.wasCanceled():
                    return
                row = {"Patient": patient_id}
                if result.get('data') and result['data'].get('variables'):
                    row.update(result['data']['variables'])
                rows.append(row)

            progress.setValue(50)
            QApplication.processEvents()

            df = pd.DataFrame(rows)
            df.to_excel(excel_path, index=False, engine='openpyxl')

            progress.setValue(100)
            CustomMessageBox.information(self, "Exportation réussie",
                                    f"Les données ont été exportées avec succès vers :\n{excel_path}")
            self.statusBar().showMessage(f"Exporté vers {excel_path}", 5000)

        except Exception as e:
            CustomMessageBox.critical(self, "Erreur d'exportation", f"Échec de l'exportation vers Excel :\n{str(e)}")
        finally:
            if 'progress' in locals() and isinstance(progress, QProgressDialog):
                progress.close()
            gc.collect()

    def closeEvent(self, event):
        reply = CustomMessageBox.question(self, 'Quitter', "Êtes-vous sûr de vouloir quitter AutoQuest ?",
                                     CustomMessageBox.Yes | CustomMessageBox.No, CustomMessageBox.No)

        if reply == CustomMessageBox.Yes:
            self.memory_timer.stop()
            gc.collect()
            event.accept()
        else:
            event.ignore()



if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            import ctypes

            myappid = u'mycompany.myproduct.subproduct.version'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        mem = psutil.virtual_memory()
        if mem.percent > 95:
            print("Erreur : Mémoire système insuffisante")
            sys.exit(1)

        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # Style global renforcé
        app.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #333333;
            }
            CustomMessageBox {
                background-color: #ffffff;
            }
            CustomMessageBox QLabel {
                color: #333333 !important;
            }
        """)

        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        error_box = CustomMessageBox()
        error_box.setStyleSheet("""
            CustomMessageBox {
                background-color: #ffffff;
            }
            QLabel {
                color: #333333;
            }
        """)
        error_box.critical(None, "Erreur", f"Échec du démarrage : {str(e)}")
        sys.exit(1)
