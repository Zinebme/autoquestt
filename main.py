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
    QProgressDialog, QSplitter
)
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- Police de base ---
        self.base_font = QtGui.QFont("Segoe UI", 10)
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
        self.setWindowIcon(QtGui.QIcon("icons/app_icon.png"))  # Suggest adding an app icon

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

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #fcfcfc;
            }
            QMenuBar {
                background-color: #fcfcfc;
                border-bottom: 1px solid #e0e0e0;
            }
            QMenuBar::item {
                padding: 6px 12px;
            }
            QMenuBar::item:selected {
                background-color: #e8e8e8;
                border-radius: 4px;
            }
            QMenu {
                background-color: #ffffff;
                border: 1px solid #dcdcdc;
                padding: 5px;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background-color: #f0f8ff; /* AliceBlue */
                color: #000;
            }
            QStatusBar {
                background: #fcfcfc;
                border-top: 1px solid #e0e0e0;
            }
            QSplitter::handle {
                background: #e0e0e0;
            }
            QSplitter::handle:horizontal {
                width: 1px;
            }
            QLabel {
                color: #333;
            }
            QMessageBox {
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QProgressDialog {
                font-family: "Segoe UI";
                font-size: 10pt;
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
        self.sidebar.setMinimumWidth(200)
        self.sidebar.setMaximumWidth(350)
        self.sidebar.setIconSize(QSize(24, 24))
        self.sidebar.setFont(QtGui.QFont("Segoe UI", 11, QFont.Bold))

        self.sidebar.setStyleSheet("""
            QListWidget {
                background-color: #2c3e50;
                color: white;
                border: none;
                outline: 0;
            }
            QListWidget::item {
                padding: 15px 20px;
                border-bottom: 1px solid #34495e;
            }
            QListWidget::item:hover {
                background-color: #34495e;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                border-left: 4px solid #ffffff;
                color: white;
            }
            QToolTip {
                background-color: #34495e;
                color: white;
                border: 1px solid #2c3e50;
                padding: 4px;
            }
        """)

        items = [
            ("Projet", "icons/project.png", "Gérer les détails du projet"),
            ("Documents", "icons/documents.png", "Visualiser et organiser les documents"),
            ("Extraction", "icons/extraction.png", "Définir les variables et extraire les données"),
            ("Vérification", "icons/verification.png", "Vérifier les données extraites"),
            ("Exportation", "icons/export.png", "Exporter les résultats finaux")
        ]

        for text, icon_path, tooltip in items:
            item = QListWidgetItem(QtGui.QIcon(icon_path), text)
            item.setToolTip(tooltip)
            self.sidebar.addItem(item)

        self.sidebar.currentRowChanged.connect(self.change_view)
        self.sidebar.setEnabled(False)

    def create_central_area(self):
        self.central_widget = QStackedWidget()
        self.central_widget.setStyleSheet("background-color: #ffffff; border: none;")

        # Vue Projet
        project_view = QWidget()
        project_layout = QVBoxLayout(project_view)
        project_layout.setAlignment(Qt.AlignCenter)
        self.project_label = QLabel("Vue Projet - Aucun projet chargé")
        self.project_label.setFont(QtGui.QFont("Segoe UI", 14, QFont.Light))
        self.project_label.setStyleSheet("color: #7f8c8d;")
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
        export_label = QLabel("Vue Exportation")
        export_label.setFont(QtGui.QFont("Segoe UI", 14, QFont.Light))
        export_label.setStyleSheet("color: #7f8c8d;")
        export_layout.addWidget(export_label)
        self.central_widget.addWidget(export_view)

    def create_menus(self):
        menu_bar = self.menuBar()

        # Menu Fichier
        file_menu = menu_bar.addMenu("&Fichier")

        new_project_action = QAction(QtGui.QIcon("icons/new.png"), "&Nouveau Projet...", self)
        new_project_action.setShortcut("Ctrl+N")
        new_project_action.triggered.connect(self.safe_new_project)
        file_menu.addAction(new_project_action)

        open_project_action = QAction(QtGui.QIcon("icons/open.png"), "&Ouvrir un Projet...", self)
        open_project_action.setShortcut("Ctrl+O")
        open_project_action.triggered.connect(self.safe_open_project)
        file_menu.addAction(open_project_action)

        self.save_action = QAction(QtGui.QIcon("icons/save.png"), "&Enregistrer", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self._save_project_data)
        self.save_action.setEnabled(False)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()

        exit_action = QAction(QtGui.QIcon("icons/exit.png"), "&Quitter", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Menu Outils
        tools_menu = menu_bar.addMenu("&Outils")

        self.import_action = QAction(QtGui.QIcon("icons/import.png"), "&Importer des Scans...", self)
        self.import_action.setShortcut("Ctrl+I")
        self.import_action.triggered.connect(self.safe_import_scans)
        self.import_action.setEnabled(False)
        tools_menu.addAction(self.import_action)

        self.scan_action = QAction(QtGui.QIcon("icons/scan.png"), "&Numériser un nouveau document...", self)
        self.scan_action.setShortcut("Ctrl+Shift+S")
        self.scan_action.triggered.connect(self.scan_new)
        self.scan_action.setEnabled(False)
        tools_menu.addAction(self.scan_action)

        tools_menu.addSeparator()

        self.extract_action = QAction(QtGui.QIcon("icons/extract.png"), "Lancer l'&extraction des données", self)
        self.extract_action.setShortcut("Ctrl+E")
        self.extract_action.triggered.connect(self.safe_extract_data)
        self.extract_action.setEnabled(False)
        tools_menu.addAction(self.extract_action)

        self.export_action = QAction(QtGui.QIcon("icons/export.png"), "&Exporter vers Excel...", self)
        self.export_action.setShortcut("Ctrl+Shift+E")
        self.export_action.triggered.connect(self.safe_export_to_excel)
        self.export_action.setEnabled(False)
        tools_menu.addAction(self.export_action)

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
            QMessageBox.critical(self, "Erreur", f"Erreur inattendue lors de la création du projet :\n{str(e)}")
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
                    QMessageBox.warning(self, "Projet invalide",
                                        "Le dossier sélectionné ne contient pas de fichier 'project.json' valide.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'ouverture du projet :\n{str(e)}")
        finally:
            gc.collect()

    def load_project(self, path):
        try:
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                QMessageBox.warning(self, "Avertissement Mémoire",
                                    "La mémoire système est trop utilisée pour charger ce projet en toute sécurité.")
                return

            self.project_path = path
            self._load_project_data()
            self.setWindowTitle(f"AutoQuest - {os.path.basename(path)}")
            self.statusBar().showMessage(f"Projet chargé : {path}")

            self.sidebar.setEnabled(True)
            self.save_action.setEnabled(True)
            self.import_action.setEnabled(True)
            self.scan_action.setEnabled(True)
            self.extract_action.setEnabled(True)
            self.export_action.setEnabled(True)

            self.project_label.setText(f"Projet : {os.path.basename(path)}")

            self.documents_view.update_view(self.project_data)
            self.variables_view.update_view(self.project_data)
            self.verification_view.update_view(self.project_data)

            self.sidebar.setCurrentRow(0)

        except Exception as e:
            QMessageBox.critical(self, "Erreur de chargement", f"Échec du chargement du projet :\n{str(e)}")
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
            QMessageBox.critical(self, "Erreur de sauvegarde", f"Échec de la sauvegarde du projet :\n{str(e)}")

    def safe_import_scans(self):
        if not self.project_path:
            return

        try:
            source_dir = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier contenant les scans",
                                                          os.path.expanduser("~"))
            if not source_dir:
                return

            if not any(f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')) for f in os.listdir(source_dir)):
                QMessageBox.warning(self, "Aucune image", "Le dossier sélectionné ne contient aucune image supportée.")
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
                QMessageBox.information(self, "Importation réussie",
                                        f"{len(self.project_data['compiled_questionnaires'])} dossiers patient ont été préparés.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur durant l'importation", str(e))
            finally:
                progress.close()
                gc.collect()

        except Exception as e:
            QMessageBox.critical(self, "Erreur d'importation", f"Échec de l'importation des scans :\n{str(e)}")
        finally:
            gc.collect()

    def safe_extract_data(self):
        if not self.project_data.get("compiled_questionnaires"):
            QMessageBox.warning(self, "Données manquantes", "Veuillez d'abord importer et organiser les scans.")
            return

        variables = self.project_data.get("variables", [])
        if not variables:
            QMessageBox.warning(self, "Aucune variable définie",
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
            QMessageBox.information(
                self,
                "Extraction terminée",
                f"Traitement terminé.\nPatients traités : {processed_count}\nPatients en erreur : {error_count}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Erreur d'extraction",
                                 f"Une erreur fatale est survenue durant l'extraction :\n{str(e)}")
        finally:
            progress.close()
            gc.collect()

    def scan_new(self):
        QMessageBox.information(self, "Non implémenté",
                                "La numérisation directe n'est pas encore disponible dans cette version.")

    def safe_export_to_excel(self):
        if not self.project_path:
            return

        data_dict = self.project_data.get('extracted_data', {})
        if not data_dict:
            QMessageBox.warning(self, "Aucune donnée", "Aucune donnée extraite à exporter.")
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
            QMessageBox.information(self, "Exportation réussie",
                                    f"Les données ont été exportées avec succès vers :\n{excel_path}")
            self.statusBar().showMessage(f"Exporté vers {excel_path}", 5000)

        except Exception as e:
            QMessageBox.critical(self, "Erreur d'exportation", f"Échec de l'exportation vers Excel :\n{str(e)}")
        finally:
            if 'progress' in locals() and isinstance(progress, QProgressDialog):
                progress.close()
            gc.collect()

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Quitter', "Êtes-vous sûr de vouloir quitter AutoQuest ?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.memory_timer.stop()
            gc.collect()
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            # Améliore l'icône de l'application dans la barre des tâches sur Windows
            import ctypes

            myappid = u'mycompany.myproduct.subproduct.version'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        mem = psutil.virtual_memory()
        if mem.percent > 95:
            print("Erreur : L'utilisation de la mémoire système est trop élevée pour démarrer l'application.")
            sys.exit(1)

        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Échec du démarrage de l'application : {str(e)}")
        # Affiche une boîte de message d'erreur si possible
        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Critical)
        error_box.setText("Erreur critique au démarrage")
        error_box.setInformativeText(f"L'application n'a pas pu démarrer.\n\nDétails : {str(e)}")
        error_box.setWindowTitle("Erreur de démarrage")
        error_box.exec_()
        sys.exit(1)
