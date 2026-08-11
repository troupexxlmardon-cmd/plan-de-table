from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import fitz  # PyMuPDF
from pyairtable import Api
import io
import os
import requests
import time
import traceback  # <-- Ajout pour capturer les détails de l'erreur

app = FastAPI(title="Générateur Plan de Table Airtable")

# ==============================================================================
# 🔑 VOS IDENTIFIANTS AIRTABLE
# ==============================================================================
AIRTABLE_TOKEN = "patUeoUFl3qVPww4b.01ee555ff3aef9d6c3993102a1438919965e1d1e3b5df4062f8f2d3d858fb948"
AIRTABLE_BASE_ID = "appqPIiZcZq2JRZpO"
TABLE_INVITES_NAME = "Tables"             # Table des invités
TABLE_DOCS_NAME = "Plan de table doc"     # Table des documents
# ==============================================================================

FONT_PATH = "Lora-Regular.ttf"

class PlanRequest(BaseModel):
    file_url: str
    record_id: str

def process_plan_in_background(file_url: str, record_id: str):
    api = Api(AIRTABLE_TOKEN)
    table_docs = api.table(AIRTABLE_BASE_ID, TABLE_DOCS_NAME)

    try:
        # 1. Téléchargement du PDF source
        pdf_response = requests.get(file_url)
        if pdf_response.status_code != 200:
            print(f"❌ Erreur de téléchargement du PDF source (Status Code: {pdf_response.status_code})")
            table_docs.update(record_id, {"Statut": "Ready"})
            return
        
        pdf_bytes = pdf_response.content

        # 2. Récupération des invités
        table_invites = api.table(AIRTABLE_BASE_ID, TABLE_INVITES_NAME)
        records = table_invites.all()

        place_info = {}
        for r in records:
            fields = r.get("fields", {})
            num_place = fields.get("Numéro place") or fields.get("Numero place") or fields.get("Place")
            raw_nom = fields.get("Nom complet")
            
            nom_invite = ""
            if isinstance(raw_nom, list) and len(raw_nom) > 0:
                nom_invite = str(raw_nom[0])
            elif isinstance(raw_nom, str):
                nom_invite = raw_nom

            col_vege_val = None
            for k, v in fields.items():
                if "végétarien" in k.lower() or "vege" in k.lower():
                    col_vege_val = v
                    break
            
            is_vege = False
            if col_vege_val:
                if isinstance(col_vege_val, list) and len(col_vege_val) > 0:
                    col_vege_val = col_vege_val[0]
                if str(col_vege_val).strip().lower() in ['oui', 'yes', 'true', '1']:
                    is_vege = True

            if num_place is not None and nom_invite and not nom_invite.startswith("rec"):
                try:
                    num_place_int = int(num_place)
                    parties = str(nom_invite).strip().split(maxsplit=1)
                    prenom = parties[0]
                    nom_famille = parties[1] if len(parties) > 1 else ""
                    
                    place_info[num_place_int] = {
                        'prenom': prenom,
                        'nom': nom_famille,
                        'is_vege': is_vege
                    }
                except (ValueError, TypeError):
                    continue

        # 3. Traitement du PDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]

        # Vérification et configuration de la police
        use_custom_font = os.path.exists(FONT_PATH)
        
        if use_custom_font:
            font = fitz.Font(fontfile=FONT_PATH)
        else:
            font = fitz.Font("helv")

        words = page.get_text("words")

        COULEUR_TEXTE_NORMAL   = (0.2, 0.2, 0.2)
        COULEUR_BORDURE_NORMAL = (0.75, 0.75, 0.75)
        COULEUR_TEXTE_VEGE     = (0.12, 0.52, 0.29)
        COULEUR_BORDURE_VEGE   = (0.12, 0.52, 0.29)
        COULEUR_FOND           = (1, 1, 1)

        for word in words:
            texte_mot = word[4].strip()
            if texte_mot.isdigit():
                num_place = int(texte_mot)
                if num_place in place_info:
                    info = place_info[num_place]
                    prenom, nom_famille, is_vege = info['prenom'], info['nom'], info['is_vege']
                    
                    x0, y0, x1, y1 = word[0], word[1], word[2], word[3]
                    centre_x, centre_y = (x0 + x1) / 2.0, (y0 + y1) / 2.0
                    centre_point = fitz.Point(centre_x, centre_y)
                    
                    RAYON = 16.0
                    couleur_texte = COULEUR_TEXTE_VEGE if is_vege else COULEUR_TEXTE_NORMAL
                    couleur_bordure = COULEUR_BORDURE_VEGE if is_vege else COULEUR_BORDURE_NORMAL
                    
                    page.draw_circle(centre_point, radius=RAYON, color=couleur_bordure, fill=COULEUR_FOND, width=0.6 if is_vege else 0.5)
                    
                    taille_police = 4.2
                    min_taille = 2.6
                    largeur_max_permise = (RAYON * 2) - 4.0
                    
                    while taille_police >= min_taille:
                        l1 = font.text_length(prenom, fontsize=taille_police)
                        l2 = font.text_length(nom_famille, fontsize=taille_police) if nom_famille else 0
                        if max(l1, l2) <= largeur_max_permise:
                            break
                        taille_police -= 0.2

                    ascent = font.ascender * taille_police
                    descent = font.descender * taille_police
                    hauteur_ligne = ascent - descent
                    interligne = hauteur_ligne * 0.20
                    
                    nb_lignes = 2 if nom_famille else 1
                    hauteur_totale_bloc = (nb_lignes * hauteur_ligne) + ((nb_lignes - 1) * interligne)
                    
                    haut_bloc = centre_y - (hauteur_totale_bloc / 2.0)
                    baseline_1 = haut_bloc + ascent
                    
                    larg_p = font.text_length(prenom, fontsize=taille_police)
                    x_p = centre_x - (larg_p / 2.0)

                    # Insertion du prénom (avec fontfile si la police existe)
                    if use_custom_font:
                        page.insert_text(fitz.Point(x_p, baseline_1), prenom, fontsize=taille_police, fontfile=FONT_PATH, color=couleur_texte)
                    else:
                        page.insert_text(fitz.Point(x_p, baseline_1), prenom, fontsize=taille_police, fontname="helv", color=couleur_texte)
                    
                    if nom_famille:
                        baseline_2 = baseline_1 + hauteur_ligne + interligne
                        larg_n = font.text_length(nom_famille, fontsize=taille_police)
                        x_n = centre_x - (larg_n / 2.0)
                        
                        # Insertion du nom (avec fontfile si la police existe)
                        if use_custom_font:
                            page.insert_text(fitz.Point(x_n, baseline_2), nom_famille, fontsize=taille_police, fontfile=FONT_PATH, color=couleur_texte)
                        else:
                            page.insert_text(fitz.Point(x_n, baseline_2), nom_famille, fontsize=taille_police, fontname="helv", color=couleur_texte)

        # Génération des octets du fichier PDF final (BLOC RÉTABLI)
        output_buffer = io.BytesIO()
        doc.save(output_buffer)
        doc.close()
        pdf_out = output_buffer.getvalue()

        # 4. Enregistrement direct dans 'Dernier plan'
        table_docs.upload_attachment(record_id, "Dernier plan", "Plan_de_table_NOMINATIF.pdf", pdf_out)
        print("✅ Fichier PDF déposé dans Airtable !")

        # 5. Gestion des statuts : Passage à 'Done', puis 'Ready' après 5 secondes
        table_docs.update(record_id, {"Statut": "Done"})
        print("STATUS: Passer à 'Done'")

        time.sleep(5)

        table_docs.update(record_id, {"Statut": "Ready"})
        print("STATUS: Retour à 'Ready'")

    except Exception as e:
        print(f"❌ Erreur pendant le traitement : {e}")
        print("🔍 TRACEBACK COMPLET :")
        print(traceback.format_exc())
        # En cas d'erreur, on remet le statut sur Ready pour débloquer l'interface
        try:
            table_docs.update(record_id, {"Statut": "Ready"})
        except Exception:
            pass

@app.get("/")
def read_root():
    return {"message": "L'API du Plan de Table fonctionne correctement !"}

@app.post("/generate-plan")
async def generate_plan(payload: PlanRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_plan_in_background, payload.file_url, payload.record_id)
    return {"status": "processing", "message": "Génération lancée en arrière-plan !"}
