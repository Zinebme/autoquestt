import os
import io
import gc
import json
import shutil
import psutil
import base64
import re
import requests
from time import sleep
from typing import List, Dict, Optional
from PIL import Image, ImageFile
import tempfile

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# API Configuration
RUNPOD_ENDPOINT = "https://j2f951zim1kgdh-8000.proxy.runpod.net/generate"

ImageFile.LOAD_TRUNCATED_IMAGES = True


def check_system_resources():
    mem = psutil.virtual_memory()
    if mem.percent > 90:
        raise MemoryError(f"Memory usage too high ({mem.percent}%)")
    if psutil.cpu_percent(interval=1) > 90:
        raise RuntimeError("CPU usage too high")


def validate_image_file(image_path: str) -> bool:
    try:
        if not os.path.exists(image_path):
            return False
        if os.path.getsize(image_path) > MAX_FILE_SIZE:
            return False
        with Image.open(image_path) as img:
            img.verify()
        return True
    except Exception:
        return False


def safe_image_open(image_path: str) -> Optional[Image.Image]:
    check_system_resources()
    try:
        img = Image.open(image_path)
        img.load()
        return img
    except Exception as e:
        print(f"Error opening image {image_path}: {str(e)}")
        return None


def preprocess_image(image_path: str) -> Optional[bytes]:
    try:
        img = safe_image_open(image_path)
        if not img:
            return None
        if img.mode != 'RGB':
            img = img.convert('RGB')
        max_dimension = 2000
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img.close()
        return img_bytes.getvalue()
    except Exception as e:
        print(f"Preprocessing failed: {str(e)}")
        return None
    finally:
        gc.collect()


def merge_images_vertically(image_paths: List[str], output_path: str) -> str:
    images = [Image.open(p).convert("RGB") for p in image_paths]
    widths = [img.width for img in images]
    heights = [img.height for img in images]
    total_height = sum(heights)
    max_width = max(widths)
    merged_image = Image.new("RGB", (max_width, total_height), color=(255, 255, 255))
    y_offset = 0
    for img in images:
        merged_image.paste(img, (0, y_offset))
        y_offset += img.height
        img.close()
    merged_image.save(output_path)
    return output_path


def call_vision_model_for_json(image_b64: str, variables_to_extract: List[str]) -> Optional[str]:
    """
    Calls the vision model with a prompt that explicitly asks for a JSON object.
    """
    json_example_keys = {key: "valeur..." for key in variables_to_extract}

    prompt = f"""Tu es un expert en extraction de données sur des formulaires médicaux.
Analyse l'image fournie et extrais les informations pour les variables suivantes : {', '.join(variables_to_extract)}.

**TACHE FINALE :**
Ta réponse DOIT être un unique objet JSON valide.
Les clés de l'objet JSON DOIVENT correspondre EXACTEMENT aux noms des variables demandées dans la liste.
Pour chaque variable de la liste, trouve la valeur correspondante dans le document.
- Si une case à cocher est cochée (symbole comme ☑, ✓, X, etc.), la valeur est "Oui".
- Si une case à cocher est vide, la valeur est "Non".
- Si une information textuelle n'est pas présente, la valeur doit être "Non renseigné" ou une chaîne vide.

Voici un exemple de la structure JSON que tu dois retourner :
```json
{json.dumps(json_example_keys, indent=2, ensure_ascii=False)}
```

Ne retourne RIEN d'autre que l'objet JSON. Pas de texte explicatif, pas de markdown, juste le JSON.
"""

    payload = {
        "prompt": prompt,
        "image_base64": image_b64,
        "max_tokens": 4096,
        "temperature": 0.0,
    }
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(RUNPOD_ENDPOINT, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            text = data.get("text") or data.get("output", "")
            print(f"\n📤 Réponse brute (JSON attendu) du modèle de vision RunPod :\n{text}\n")
            return text.strip()
        except Exception as e:
            print(f"⚠️ Tentative d'appel au modèle de vision {attempt + 1} échouée : {str(e)}")
            if attempt == MAX_RETRIES - 1:
                return f"ERROR: {str(e)}"
            sleep(RETRY_DELAY)
    return "ERROR: L'appel au modèle de vision a échoué après plusieurs tentatives."


def parse_json_response(json_string: str) -> Optional[dict]:
    """
    Parses the JSON string returned by the model.
    """
    match = re.search(r'\{.*\}', json_string, re.DOTALL)
    if not match:
        print("Erreur de parsing : Aucun objet JSON trouvé dans la réponse du modèle.")
        return None
    clean_json_str = match.group(0)
    try:
        return json.loads(clean_json_str)
    except json.JSONDecodeError:
        print("Erreur de parsing : La réponse du modèle n'est pas un JSON valide.")
        return None


def consolidate_group_results(model_output: dict, original_variables: List[Dict], warnings: List[str]) -> dict:
    """
    Consolidates the results for 'group' type variables into a single key-value pair,
    handling conflicts where multiple options are checked.
    """
    final_results = {}
    model_output_lower = {k.lower(): v for k, v in model_output.items()}

    for var_spec in original_variables:
        var_name = var_spec['name']
        var_type = var_spec.get('type', 'text')

        if var_type == 'group':
            checked_options = []
            for option in var_spec.get('options', []):
                sub_var_name = f"{var_name}: {option}".lower()
                if model_output_lower.get(sub_var_name, "Non").lower() == 'oui':
                    checked_options.append(option)

            if len(checked_options) == 1:
                final_results[var_name] = checked_options[0]
            elif len(checked_options) > 1:
                warning_msg = f"Conflit pour '{var_name}': Plusieurs options cochées détectées ({', '.join(checked_options)})"
                warnings.append(warning_msg)
                final_results[var_name] = ', '.join(checked_options)
            else:  # len(checked_options) == 0
                final_results[var_name] = "Non renseigné"
        else:
            # For text types, find the value directly
            final_results[var_name] = model_output_lower.get(var_name.lower(), "Non renseigné")

    return final_results


def call_vision_model_for_variable_detection(image_b64: str) -> Optional[str]:
    """
    Calls the vision model with a prompt that asks for variable detection.
    """
    prompt = """Tu es un expert en analyse de formulaires.
Analyse l'image fournie et identifie TOUS les champs de formulaire, les étiquettes de données, et les questions qui pourraient être des variables à extraire.

**Instructions :**
1.  Liste les noms de ces variables dans l'ordre où ils apparaissent sur le document, de haut en bas.
2.  Sois concis mais descriptif. Par exemple, "Date de naissance" est mieux que "Date".
3.  Ignore les instructions, les titres généraux du document ou les paragraphes de texte. Concentre-toi sur les paires clé-valeur.

**TACHE FINALE :**
Ta réponse DOIT être un unique objet JSON valide.
L'objet JSON doit avoir une seule clé nommée "variables".
La valeur de "variables" doit être une liste de chaînes de caractères, où chaque chaîne est un nom de variable détecté.

**Exemple de format de réponse :**
```json
{
  "variables": [
    "Nom du patient",
    "Prénom du patient",
    "Date de naissance",
    "Sexe",
    "Symptôme principal",
    "Date d'apparition des symptômes",
    "Antécédents médicaux"
  ]
}
```

Ne retourne RIEN d'autre que l'objet JSON. Pas de texte explicatif, pas de markdown, juste le JSON.
"""

    payload = {
        "prompt": prompt,
        "image_base64": image_b64,
        "max_tokens": 4096,
        "temperature": 0.0,
    }
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(RUNPOD_ENDPOINT, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            text = data.get("text") or data.get("output", "")
            print(f"\n📤 Réponse brute (détection de variables) du modèle de vision RunPod :\n{text}\n")
            return text.strip()
        except Exception as e:
            print(f"⚠️ Tentative d'appel au modèle de vision {attempt + 1} échouée : {str(e)}")
            if attempt == MAX_RETRIES - 1:
                return f"ERROR: {str(e)}"
            sleep(RETRY_DELAY)
    return "ERROR: L'appel au modèle de vision a échoué après plusieurs tentatives."


def detect_variables_from_image_folder(folder_path: str) -> Dict:
    """
    Analyzes the images in a folder to detect potential variables.
    """
    results_wrapper = {
        "variables": [], "errors": [], "warnings": []
    }
    print(f"\n📂 Lancement de la détection de variables pour le dossier : {folder_path}")

    try:
        images = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
                        key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'([0-9]+)', x)])
        if not images:
            raise FileNotFoundError("Aucune image trouvée dans le dossier.")

        full_image_paths = [os.path.join(folder_path, img) for img in images]

        print("⏳ Fusion des images pour la détection...")
        merged_path = os.path.join(tempfile.gettempdir(), "merged_detection.png")
        merge_images_vertically(full_image_paths, merged_path)

        if not validate_image_file(merged_path):
            raise ValueError(f"L'image fusionnée est invalide: {merged_path}")

        image_data = preprocess_image(merged_path)
        if not image_data:
            raise ValueError("Échec du prétraitement de l'image.")

        encoded_image = base64.b64encode(image_data).decode("utf-8")

        print("🤖 Appel du modèle de vision pour la détection de variables...")
        raw_response = call_vision_model_for_variable_detection(encoded_image)

        if not raw_response or raw_response.startswith("ERROR"):
            raise ValueError(f"Erreur du modèle de vision : {raw_response}")

        print("✅ Réponse reçue, parsing du JSON...")
        parsed_data = parse_json_response(raw_response)
        if not parsed_data or "variables" not in parsed_data or not isinstance(parsed_data["variables"], list):
            raise ValueError("La réponse JSON du modèle est mal formée ou ne contient pas de liste de variables.")

        detected_vars = parsed_data["variables"]
        print(f"🔎 Variables détectées : {detected_vars}")
        results_wrapper["variables"] = detected_vars

    except Exception as e:
        results_wrapper["errors"].append(str(e))
        print(f"❌ Erreur générale lors de la détection : {str(e)}")

    print("\n✅ Détection de variables terminée.\n")
    return results_wrapper


def extract_data_from_image_folder(folder_path: str, variables: List[Dict]) -> Dict:
    results_wrapper = {
        "pages": [], "errors": [], "variables": {}, "warnings": []
    }
    print(f"\n📂 Traitement du dossier : {folder_path}")
    print(f"🔎 Variables définies par l'utilisateur : {variables}\n")

    try:
        images = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
                        key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'([0-9]+)', x)])
        if not images:
            raise FileNotFoundError("Aucune image trouvée dans le dossier.")

        full_image_paths = [os.path.join(folder_path, img) for img in images]

        print("⏳ Fusion des images...")
        merged_path = os.path.join(tempfile.gettempdir(), "merged_patient.png")
        merge_images_vertically(full_image_paths, merged_path)

        if not validate_image_file(merged_path):
            raise ValueError(f"L'image fusionnée est invalide: {merged_path}")

        image_data = preprocess_image(merged_path)
        if not image_data:
            raise ValueError("Échec du prétraitement de l'image.")

        encoded_image = base64.b64encode(image_data).decode("utf-8")

        # Build the list of variables to query the model
        variables_to_extract = []
        for var in variables:
            if var.get('type') == 'group':
                for option in var.get('options', []):
                    variables_to_extract.append(f"{var['name']}: {option}")
            else:
                variables_to_extract.append(var['name'])

        print(f"🤖 Appel du modèle de vision avec les sous-questions pour les groupes...")
        raw_response = call_vision_model_for_json(encoded_image, variables_to_extract)

        if not raw_response or raw_response.startswith("ERROR"):
            raise ValueError(f"Erreur du modèle de vision : {raw_response}")

        print("✅ Réponse reçue, parsing du JSON...")
        parsed_data = parse_json_response(raw_response)
        if not parsed_data:
            raise ValueError("Impossible de parser la réponse JSON du modèle.")

        print("🔄 Consolidation des résultats des groupes...")
        final_data = consolidate_group_results(parsed_data, variables, results_wrapper["warnings"])

        print("📊 Données finales structurées :")
        for k, v in final_data.items():
            print(f"  {k}: {v}")

        results_wrapper["variables"] = final_data
        results_wrapper["pages"].append({
            "filename": "MERGED_IMAGE", "text": raw_response,
            "structured": json.dumps(final_data, ensure_ascii=False), "path": "MERGED_VIRTUAL"
        })

    except Exception as e:
        results_wrapper["errors"].append(str(e))
        print(f"❌ Erreur générale : {str(e)}")

    print("\n✅ Traitement terminé.\n")
    return results_wrapper


def prepare_patient_folders(source_dir: str, output_dir: str, pages_per_questionnaire: int) -> List[Dict]:
    # This function remains unchanged
    questionnaires = []
    try:
        images = sorted([f for f in os.listdir(source_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
                        key=lambda x: [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', x)])
        os.makedirs(output_dir, exist_ok=True)
        for i in range(0, len(images), pages_per_questionnaire):
            check_system_resources()
            batch = images[i:i + pages_per_questionnaire]
            patient_num = (i // pages_per_questionnaire) + 1
            patient_dir = os.path.join(output_dir, f"Patient_{patient_num:03d}")
            os.makedirs(patient_dir, exist_ok=True)
            source_images = []
            for idx, img_file in enumerate(batch):
                src_path = os.path.join(source_dir, img_file)
                ext = os.path.splitext(img_file)[1]
                dest_path = os.path.join(patient_dir, f"page_{idx + 1:02d}{ext}")
                try:
                    shutil.copy2(src_path, dest_path)
                    source_images.append(dest_path)
                except Exception as e:
                    print(f"Error copying {src_path}: {str(e)}")
            questionnaires.append({
                'patient_dir': patient_dir,
                'source_images': source_images,
                'questionnaire_num': patient_num
            })
            if len(questionnaires) % 5 == 0:
                gc.collect()
    except Exception as e:
        print(f"Error preparing folders: {str(e)}")
    finally:
        gc.collect()
    return questionnaires
