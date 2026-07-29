import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from pyairtable import Api
import io
import os

# ==============================================================================
# 🔑 VOS IDENTIFIANTS AIRTABLE (Remplacez les valeurs ci-dessous)
# ==============================================================================
AIRTABLE_TOKEN = "patUDyHWRx3FrQSqn.3ed2ae1fdae0357ba030ddbb947a06283860ff50f2e1fa9885977aaeda19add2"  # Votre Personal Access Token
AIRTABLE_BASE_ID = "appqPIiZcZq2JRZpO"               # Votre Base ID
AIRTABLE_TABLE_NAME = "Tables"                       # Nom exact de la table dans Airtable
# ==============================================================================

FONT_PATH = "Lora-Regular.ttf"

st.set_page_config(page_title="Générateur de Plan de Table", page_icon="🪑", layout="centered")

st.title("🪑 Générateur de Plan de Table Nominatif")

COULEUR_TEXTE_NORMAL   = (0.2, 0.2, 0.2)
COULEUR_BORDURE_NORMAL = (0.75, 0.75, 0.75)
COULEUR_TEXTE_VEGE     = (0.12, 0.52, 0.29)
COULEUR_BORDURE_VEGE   = (0.12, 0.52, 0.29)
COULEUR_FOND           = (1, 1, 1)

pdf_file = st.file_uploader("Déposez le PDF Canva", type=["pdf"])

if st.button("🚀 Générer le plan de table", type="primary", use_container_width=True):
    if not pdf_file:
        st.error("Veuillez déposer le fichier PDF Canva.")
    else:
        try:
            api = Api(AIRTABLE_TOKEN)
            table = api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
            records = table.all()

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

            # Traitement du PDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc[0]

            font_name_use = "helv"
            if os.path.exists(FONT_PATH):
                font_name_use = "Lora"
                page.insert_font(fontname="Lora", fontfile=FONT_PATH)

            words = page.get_text("words")

            for word in words:
                texte_mot = word[4].strip()
                
                if texte_mot.isdigit():
                    num_place = int(texte_mot)
                    
                    if num_place in place_info:
                        info = place_info[num_place]
                        prenom = info['prenom']
                        nom_famille = info['nom']
                        is_vege = info['is_vege']
                        
                        x0, y0, x1, y1 = word[0], word[1], word[2], word[3]
                        
                        # --- CALCUL DU CENTRE DU ROND ---
                        centre_x = (x0 + x1) / 2.0
                        centre_y = (y0 + y1) / 2.0
                        centre_point = fitz.Point(centre_x, centre_y)
                        
                        # RAYON DU ROND (Ajustable si vous voulez un rond plus grand ou plus petit)
                        RAYON = 15.0
                        
                        couleur_texte = COULEUR_TEXTE_VEGE if is_vege else COULEUR_TEXTE_NORMAL
                        couleur_bordure = COULEUR_BORDURE_VEGE if is_vege else COULEUR_BORDURE_NORMAL
                        
                        # 1. DESSIN DU ROND BLANC AVEC LA BORDURE (VERTE OU GRISE)
                        page.draw_circle(
                            centre_point, 
                            radius=RAYON, 
                            color=couleur_bordure, 
                            fill=COULEUR_FOND, 
                            width=0.6 if is_vege else 0.5
                        )
                        
                        # 2. ZONE POUR ÉCRIRE LE TEXTE AU CENTRE DU ROND
                        rect_pave = fitz.Rect(
                            centre_x - RAYON, 
                            centre_y - RAYON, 
                            centre_x + RAYON, 
                            centre_y + RAYON
                        )
                        
                        FONT_SIZE = 4.2
                        
                        if nom_famille:
                            rect_prenom = fitz.Rect(rect_pave.x0, rect_pave.y0 + 2.5, rect_pave.x1, centre_y + 1.0)
                            rect_nom = fitz.Rect(rect_pave.x0, centre_y - 1.0, rect_pave.x1, rect_pave.y1 - 2.0)
                            page.insert_textbox(rect_prenom, prenom, fontsize=FONT_SIZE, fontname=font_name_use, color=couleur_texte, align=fitz.TEXT_ALIGN_CENTER)
                            page.insert_textbox(rect_nom, nom_famille, fontsize=FONT_SIZE, fontname=font_name_use, color=couleur_texte, align=fitz.TEXT_ALIGN_CENTER)
                        else:
                            rect_seul = fitz.Rect(rect_pave.x0, centre_y - 3.0, rect_pave.x1, centre_y + 3.0)
                            page.insert_textbox(rect_seul, prenom, fontsize=FONT_SIZE, fontname=font_name_use, color=couleur_texte, align=fitz.TEXT_ALIGN_CENTER)

            output_buffer = io.BytesIO()
            doc.save(output_buffer)
            doc.close()
            output_buffer.seek(0)

            st.success("🎉 Plan de table généré avec succès !")

            st.download_button(
                label="📥 Télécharger le Plan de Table PDF",
                data=output_buffer,
                file_name="Plan_de_table_NOMINATIF.pdf",
                mime="application/pdf",
                type="primary"
            )

        except Exception as e:
            st.error(f"Erreur : {e}")
