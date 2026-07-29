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
                        
                        centre_x = (x0 + x1) / 2.0
                        centre_y = (y0 + y1) / 2.0
                        centre_point = fitz.Point(centre_x, centre_y)
                        
                        RAYON = 16.0
                        
                        couleur_texte = COULEUR_TEXTE_VEGE if is_vege else COULEUR_TEXTE_NORMAL
                        couleur_bordure = COULEUR_BORDURE_VEGE if is_vege else COULEUR_BORDURE_NORMAL
                        
                        # 1. Dessin du cercle
                        page.draw_circle(
                            centre_point, 
                            radius=RAYON, 
                            color=couleur_bordure, 
                            fill=COULEUR_FOND, 
                            width=0.6 if is_vege else 0.5
                        )
                        
                        # 2. Définition du rectangle de saisie élargi et recentré verticalement
                        # Le décalage (+1.0) permet d'abaisser légèrement le texte pour un centrage parfait dans le rond
                        LARGEUR_BOITE = RAYON * 0.95
                        HAUTEUR_BOITE = RAYON * 0.75
                        
                        rect_texte = fitz.Rect(
                            centre_x - LARGEUR_BOITE,
                            centre_y - HAUTEUR_BOITE + 1.0,
                            centre_x + LARGEUR_BOITE,
                            centre_y + HAUTEUR_BOITE + 1.0
                        )
                        
                        texte_complet = f"{prenom}\n{nom_famille}" if nom_famille else prenom
                        lignes_attendues = 2 if nom_famille else 1
                        
                        # 3. Recherche automatique de la taille de police idéale
                        taille_police = 4.2
                        min_taille = 2.6
                        pas = 0.2
                        
                        while taille_police >= min_taille:
                            # Test pour vérifier si le texte rentre sans créer de lignes supplémentaires
                            res = page.insert_textbox(
                                rect_texte, 
                                texte_complet, 
                                fontsize=taille_police, 
                                fontname=font_name_use, 
                                color=couleur_texte, 
                                align=fitz.TEXT_ALIGN_CENTER,
                                render_mode=3  # Mode invisible pour le test
                            )
                            # Si res >= 0, le texte rentre parfaitement dans la boîte
                            if res >= 0:
                                break
                            taille_police -= pas

                        # 4. Insertion définitive du texte avec la bonne taille
                        page.insert_textbox(
                            rect_texte, 
                            texte_complet, 
                            fontsize=taille_police, 
                            fontname=font_name_use, 
                            color=couleur_texte, 
                            align=fitz.TEXT_ALIGN_CENTER
                        )

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
