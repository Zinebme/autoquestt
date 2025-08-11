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
from difflib import get_close_matches
from PIL import Image, ImageFile
import tempfile
from datetime import datetime
import unicodedata

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# API Configuration
RUNPOD_ENDPOINT = "https://gcxin0eoszxqb6-8000.proxy.runpod.net/generate"

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


def raw_text_ocr_with_qwen(image_paths) -> str:
    if isinstance(image_paths, str):
        image_paths = [image_paths]
    check_system_resources()

    merged_path = os.path.join(tempfile.gettempdir(), "merged_patient.png")
    merge_images_vertically(image_paths, merged_path)

    if not validate_image_file(merged_path):
        return f"ERROR: Invalid image: {merged_path}"

    image_data = preprocess_image(merged_path)
    if not image_data:
        return f"ERROR: Preprocessing failed: {merged_path}"

    encoded_image = base64.b64encode(image_data).decode("utf-8")

    # Prompt clair pour extraction brute
    prompt = (
        "Tu es un assistant OCR médical pour formulaires multi-pages.\n"
        "Lis attentivement toutes les pages fusionnées et regroupe les données.\n\n"
        "📌 Règles :\n"
        "1. Pour une case cochée ([X], ☑, ✓, ✔, 1) → 'Oui'.\n"
        "2. Pour une case vide ([ ], ☐, 0) → 'Non'.\n"
        "3. Ne garder que l’option cochée si plusieurs options.\n"
        "4. Format strict : Champ: Valeur — un par ligne.\n"
        "5. Pas de texte explicatif, pas de crochets, pas de symboles.\n"
        "6. Inclure toutes les infos présentes visuellement.\n\n"
        "Exemple :\n"
        "Fièvre: Oui\n"
        "Toux: Non\n"
        "Résultats: Positif\n"
        "Evolution: Guérison\n"
    )

    payload = {
        "prompt": prompt,
        "image_base64": encoded_image
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(RUNPOD_ENDPOINT, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            text = data.get("text") or data.get("output", "")
            text = text.strip()
            print(f"\n📤 Réponse OCR brute du modèle RunPod pour {os.path.basename(merged_path)} :\n{text}\n")
            return text
        except Exception as e:
            print(f"⚠️ Tentative {attempt + 1} échouée : {str(e)}")
            if attempt == MAX_RETRIES - 1:
                return f"ERROR: {str(e)}"
            sleep(RETRY_DELAY)
    return "ERROR: OCR failed after retries"


import unicodedata
import re
from difflib import get_close_matches


def normalize_label(label: str) -> str:
    label = label.lower()
    label = unicodedata.normalize('NFKD', label)
    label = label.encode('ascii', 'ignore').decode('ascii')  # enlève accents
    label = re.sub(r'\([^)]*\)', '', label)  # enlève parenthèses et leur contenu
    label = re.sub(r'[^a-z0-9\s]', ' ', label)  # ne garde que lettres, chiffres, espaces
    label = re.sub(r'\s+', ' ', label).strip()
    # corrections fréquentes
    label = label.replace("willaya", "wilaya")
    label = label.replace("mdie", "maladie")
    return label


def parse_structured_response(raw_text: str, variables) -> dict:
    # --- Step 1: Raw data extraction ---
    # First, parse the entire raw text into a dictionary of {raw_key: raw_value}
    # This captures all information before we try to match it to our variables.
    raw_data = {}
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    for line in lines:
        # Try parsing the markdown list format (e.g., "- **Key**: Value")
        match = re.match(r'^\s*-\s*\*\*(.*?)\*\*:\s*(.*)$', line)

        # If not, try parsing the markdown table format (e.g., "| Key | Value |")
        if not match:
            match = re.match(r'^\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|?\s*$', line)

        # If not, try parsing the plain key-value format (e.g., "Key: Value")
        if not match:
            match = re.match(r'^\s*(.*?)\s*:\s*(.*)$', line)

        if not match:
            continue

        raw_key, raw_value = match.groups()
        if raw_key.strip().startswith('---') or not raw_key.strip():
            continue
        raw_data[raw_key.strip()] = raw_value.strip()

    # --- Step 2: Two-pass matching and value processing ---
    # Now, iterate through the variables we NEED, and find the best match from the raw data.
    results = {}
    mappings = {}

    # Create a map of normalized_key -> original_key for all extracted raw keys
    # Heuristic: For matching, only consider text before a '/' to improve accuracy for long field names.
    norm_to_raw_key_map = {normalize_label(k.split('/')[0].strip()): k for k in raw_data.keys()}

    for var_spec in variables:
        var_name = var_spec['name'] if isinstance(var_spec, dict) else var_spec
        norm_var_name = normalize_label(var_name)

        best_raw_key = None
        # Prioritize exact match
        if norm_var_name in norm_to_raw_key_map:
            best_raw_key = norm_to_raw_key_map[norm_var_name]
        else:
            # Fallback to fuzzy matching if no exact match is found
            closest_norm_keys = get_close_matches(norm_var_name, list(norm_to_raw_key_map.keys()), n=1, cutoff=0.6)
            if closest_norm_keys:
                best_raw_key = norm_to_raw_key_map[closest_norm_keys[0]]

        if best_raw_key:
            raw_value = raw_data[best_raw_key]
            value = raw_value

            # --- Boolean conversion logic ---
            is_bool = False
            # Use the user's enhanced pattern for checked boxes
            if re.fullmatch(r'oui|yes|\[x\]|\[X\]|☑|☒|✓|✔|■|▣|●|◉|1|✗|✘', value, re.IGNORECASE):
                value = "Oui"
                is_bool = True
            # Use an enhanced pattern for unchecked boxes
            elif re.fullmatch(r'non|no|0|\[\s*\]|\[\]|☐|□|○|◯', value, re.IGNORECASE):
                value = "Non"
                is_bool = True

            # --- Defensive check for non-boolean fields ---
            boolean_fields = ['fièvre', 'toux', 'asthénie', 'anosmie', 'dyspnée', 'douleurs musculaires', 'grossesse',
                              'patient intubé', 'tdm thoracique', 'contact étroit avec un cas']
            if norm_var_name not in boolean_fields and is_bool:
                value = raw_value

            results[var_name] = value
            mappings[best_raw_key] = var_name
        else:
            results[var_name] = "Non renseigné"

    # --- Step 3: Specialized symptom parsing ---
    symptom_vars = ['Fièvre', 'Toux', 'Asthénie', 'anosmie', 'dyspnée', 'douleurs musculaires']
    symptom_line_text = ""
    for k, v in raw_data.items():
        # Check for both English "symptom" and French "symptome"
        norm_k = normalize_label(k)
        if "symptom" in norm_k or "symptome" in norm_k:
            symptom_line_text = v.lower()
            break

    if symptom_line_text:
        for var_name in symptom_vars:
            if results.get(var_name) == "Non renseigné":
                if var_name.lower() in symptom_line_text:
                    results[var_name] = "Oui"

    # Final pass to ensure all requested variables have a value
    for var_spec in variables:
        vname = var_spec['name'] if isinstance(var_spec, dict) else var_spec
        if vname not in results:
            results[vname] = "Non renseigné"

    results["_mappings"] = mappings
    return results

def parse_checkbox(line):
    if "| Oui |" in line or "[X]" in line:
        return True
    elif "| Non |" in line or "[ ]" in line:
        return False
    return None


def validate_text_fields(results: Dict) -> Dict:
    """
    Vérifie si certains champs texte (Nom, Prénom, Adresse...) sont présents
    dans les données brutes mais marqués 'Non renseigné',
    et les rétablit si possible.
    """
    text_fields = ['Nom', 'Prénom', 'Adresse du patient', 'Commune']
    for field in text_fields:
        raw_key = f'_raw_{field}'
        if raw_key in results:
            if results.get(field) == "Non renseigné" and len(results[raw_key].strip()) > 1:
                results[field] = results[raw_key]
    return results


def extract_data_from_image_folder(folder_path: str, variables: List[Dict]) -> Dict:
    results = {
        "pages": [],
        "errors": [],
        "variables": {},
        "warnings": []
    }
    print(f"\n📂 Traitement du dossier : {folder_path}")
    print(f"🔎 Variables attendues : {[v['name'] if isinstance(v, dict) else str(v) for v in variables]}\n")

    try:
        images = sorted(
            [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
            key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'([0-9]+)', x)]
        )
        if not images:
            print("❌ Aucune image trouvée.")
            results["errors"].append("No images found in folder")
            return results

        full_image_paths = [os.path.join(folder_path, img) for img in images]
        print(f"\n🖼️ Images détectées : {len(images)} pages → {full_image_paths}")
        print("⏳ Fusion et extraction OCR en cours...")

        raw_text = raw_text_ocr_with_qwen(full_image_paths)
        if raw_text.startswith("ERROR"):
            print(f"❌ Erreur OCR : {raw_text}")
            raise ValueError(raw_text)

        print("✅ Texte brut OCR :")
        print("-" * 40)
        print(raw_text)
        print("-" * 40)

        # Parsing local structuré à partir du texte brut
        structured = parse_structured_response(raw_text, variables)
        structured = validate_text_fields(structured)

        print("📊 Données structurées :")
        for k, v in structured.items():
            if not k.startswith("_"):
                print(f"  {k}: {v}")

        extracted_data = {var['name'] if isinstance(var, dict) else str(var):
                              structured.get(var['name'] if isinstance(var, dict) else str(var), "Non renseigné")
                          for var in variables}

        results["pages"].append({
            "filename": "MERGED_IMAGE",
            "text": raw_text,
            "structured": json.dumps(structured, ensure_ascii=False),
            "path": "MERGED_VIRTUAL"
        })

        if 'Nom' in structured and structured.get('Nom') == "Non renseigné":
            warning_msg = f"⚠️ Nom non détecté dans l’image fusionnée"
            print(warning_msg)
            results["warnings"].append(warning_msg)

        results["variables"] = extracted_data
    except Exception as e:
        results["errors"].append(str(e))
        print(f"❌ Erreur générale : {str(e)}")

    print("\n✅ Traitement terminé.\n")
    return results


def prepare_patient_folders(source_dir: str, output_dir: str, pages_per_questionnaire: int) -> List[Dict]:
    questionnaires = []
    try:
        images = sorted(
            [f for f in os.listdir(source_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
            key=lambda x: [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', x)]
        )

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