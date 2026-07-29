import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from pyairtable import Api
import io

# ==============================================================================
# 🔑 VOS IDENTIFIANTS AIRTABLE (Remplacez les valeurs ci-dessous)
# ==============================================================================
AIRTABLE_TOKEN = "patUDyHWRx3FrQSqn.3ed2ae1fdae0357ba030ddbb947a06283860ff50f2e1fa9885977aaeda19add2"  # Votre Personal Access Token
AIRTABLE_BASE_ID = "appqPIiZcZq2JRZpO"               # Votre Base ID
AIRTABLE_TABLE_NAME = "Tables"                       # Nom exact de la table dans Airtable
# ==============================================================================

st.set_page_config(page_title="Générateur de Plan de Table", page_icon="🪑", layout="centered")

st.title("🪑 Générateur de Plan de Table Nominatif")
st.write("Déposez votre PDF Canva pour générer automatiquement votre plan à jour depuis Airtable.")

# --- COULEURS RGB (valeurs entre 0 et 1) ---
COULEUR_TEXTE_NORMAL   = (0.2, 0.2, 0.2)     # Noir / Gris foncé
COULEUR_BORDURE_NORMAL = (0.75, 0.75, 0.75)  # Gris clair

COULEUR_TEXTE_VEGE     = (0.12, 0.52, 0.29)  # Vert
COULEUR_BORDURE_VEGE   = (0.12, 0.52, 0.29)  # Vert assorti

COULEUR_FOND           = (1, 1, 1)           # Blanc

pdf_file = st.file_uploader("Déposez le PDF Canva (ex: plan_de_table_canva.pdf)", type=["pdf"])

if st.button("🚀 Générer le plan de table", type="primary", use_container_width=True):
    if not pdf_file:
        st.error("Veuillez déposer le fichier PDF Canva.")
    else:
        try:
            # 1. Connexion et Récupération des données Airtable
            with st.spinner("Récupération des données Airtable en direct..."):
                api = Api(AIRTABLE_TOKEN)
                table = api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
                records = table.all()

            place_info = {}
            for r in records:
                fields = r.get("fields", {})
                
                num_place = fields.get("Numéro place")
                
                # --- Récupération spécifique du nom dans la colonne 'Invité' ---
                nom_invite = ""
                
                # On cherche la valeur du champ 'Invité'
                raw_val = None
                for k, v in fields.items():
                    # Priorité à la colonne 'Invité' exacte ou au Lookup 'Invité (from...)'
                    # tout en ignorant les colonnes contenant 'végétarien'
                    if k.strip() == "Invité" or ("invité" in k.lower() and "végétarien" not in k.lower() and "vege" not in k.lower()):
                        raw_val = v
                        break

                if isinstance(raw_val, list) and len(raw_val) > 0:
                    nom_invite = str(raw_val[0])
                elif isinstance(raw_val, str):
                    nom_invite = raw_val

                # --- Récupération du statut végétarien ---
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

                # Découpage du prénom et du nom si le nom est bien une chaîne valide
                if num_place and nom_invite and not nom_invite.startswith("rec"):
                    try:
                        num_place = int(num_place)
                        parties = str(nom_invite).strip().split(maxsplit=1)
                        prenom = parties[0]
                        nom_famille = parties[1] if len(parties) > 1 else ""
                        
                        place_info[num_place] = {
                            'prenom': prenom,
                            'nom': nom_famille,
                            'is_vege': is_vege
                        }
                    except (ValueError, TypeError):
                        continue

            # 2. Traitement du PDF Canva
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc[0]

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
                        
                        MARGE_X = 16.0
                        MARGE_Y = 10.0
                        
                        rect_pave = fitz.Rect(x0 - MARGE_X, y0 - MARGE_Y, x1 + MARGE_X, y1 + MARGE_Y)
                        
                        couleur_texte = COULEUR_TEXTE_VEGE if is_vege else COULEUR_TEXTE_NORMAL
                        couleur_bordure = COULEUR_BORDURE_VEGE if is_vege else COULEUR_BORDURE_NORMAL
                        
                        # Dessin du pavé blanc avec la bordure (verte pour végétarien, grise sinon)
                        page.draw_rect(
                            rect_pave, 
                            color=couleur_bordure, 
                            fill=COULEUR_FOND, 
                            width=0.6 if is_vege else 0.5
                        )
                        
                        FONT_SIZE = 4.5
                        
                        # Écriture du prénom et du nom
                        if nom_famille:
                            rect_prenom = fitz.Rect(rect_pave.x0, rect_pave.y0 + 1.0, rect_pave.x1, rect_pave.y0 + MARGE_Y + 1.0)
                            rect_nom = fitz.Rect(rect_pave.x0, rect_pave.y0 + MARGE_Y - 2.0, rect_pave.x1, rect_pave.y1 - 1.0)
                            page.insert_textbox(rect_prenom, prenom, fontsize=FONT_SIZE, fontname="helv", color=couleur_texte, align=fitz.TEXT_ALIGN_CENTER)
                            page.insert_textbox(rect_nom, nom_famille, fontsize=FONT_SIZE, fontname="helv", color=couleur_texte, align=fitz.TEXT_ALIGN_CENTER)
                        else:
                            rect_seul = fitz.Rect(rect_pave.x0, rect_pave.y0 + (MARGE_Y / 2), rect_pave.x1, rect_pave.y1 - (MARGE_Y / 2))
                            page.insert_textbox(rect_seul, prenom, fontsize=FONT_SIZE, fontname="helv", color=couleur_texte, align=fitz.TEXT_ALIGN_CENTER)

            # 3. Export du PDF
            output_buffer = io.BytesIO()
            doc.save(output_buffer)
            doc.close()
            output_buffer.seek(0)

            st.success("🎉 Plan de table généré avec succès en direct depuis Airtable !")
            
            st.download_button(
                label="📥 Télécharger le Plan de Table PDF",
                data=output_buffer,
                file_name="Plan_de_table_NOMINATIF.pdf",
                mime="application/pdf",
                type="primary"
            )

        except Exception as e:
            st.error(f"Erreur lors de la génération : {e}")

        except Exception as e:
            st.error(f"Erreur lors de la génération : {e}")
