import os
import io
from typing import Dict, List
import streamlit as st

from fiche_cuisine_app import ocr
from fiche_cuisine_app import menu_parser
from fiche_cuisine_app import matcher
from fiche_cuisine_app import pdf_gen

st.set_page_config(page_title="Fiche Cuisine", page_icon="🍽️", layout="wide")

if "lexicon" not in st.session_state:
    st.session_state.lexicon = {k: [] for k in menu_parser.SECTION_KEYWORDS.keys()}
if "reservations" not in st.session_state:
    st.session_state.reservations: List[Dict] = []

st.title("Fiche Cuisine (FR/NL)")

with st.expander("Configuration Tesseract", expanded=False):
    tess = st.text_input("Tesseract path (si non dans PATH)", value=os.environ.get("TESSERACT_CMD", ""))
    if st.button("Appliquer"):
        if tess and os.path.exists(tess):
            os.environ["TESSERACT_CMD"] = tess
            st.success("Chemin Tesseract enregistré. Relancez l'analyse si nécessaire.")
        else:
            st.warning("Chemin invalide.")

menu_tab, notes_tab, export_tab = st.tabs(["1) Menus PDF → Lexique", "2) Réservations → Plats", "3) Générer PDF"]) 

with menu_tab:
    st.subheader("Importer vos menus (PDF FR/NL)")
    pdf_files = st.file_uploader("PDFs de menu", type=["pdf"], accept_multiple_files=True)
    if st.button("Construire/Mettre à jour le lexique") and pdf_files:
        combined = {k: list(st.session_state.lexicon.get(k, [])) for k in st.session_state.lexicon.keys()}
        for up in pdf_files:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
                tf.write(up.getbuffer())
                tmp_path = tf.name
            text = menu_parser.extract_menu_text(tmp_path)
            lex = menu_parser.build_lexicon_from_text(text)
            combined = menu_parser.merge_lexicons(combined, lex)
        st.session_state.lexicon = combined
        st.success("Lexique mis à jour.")
    st.write("Lexique actuel (éditable):")
    for sec in st.session_state.lexicon.keys():
        st.markdown(f"**{sec.title()}**")
        values = st.session_state.lexicon.get(sec, [])
        text_val = "\n".join(values)
        new_text = st.text_area(f"{sec}", value=text_val, height=120, key=f"lex_{sec}")
        st.session_state.lexicon[sec] = [v.strip() for v in new_text.splitlines() if v.strip()]

with notes_tab:
    st.subheader("Importer vos captures d'écran de réservations")
    imgs = st.file_uploader("Images (PNG/JPG)", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
    if st.button("Analyser les images") and imgs:
        st.session_state.reservations = []
        for up in imgs:
            raw = up.getvalue()
            full_text, notes = ocr.notes_from_image_bytes(raw)
            # Create one reservation per note block
            if not notes:
                notes = [""]
            for note in notes:
                items = matcher.match_note_to_items(note, st.session_state.lexicon)
                st.session_state.reservations.append({
                    "name": "",
                    "time": "",
                    "pax": "",
                    "note": note,
                    "items": items,
                })
        st.success(f"{len(st.session_state.reservations)} réservation(s) détectée(s).")

    if st.session_state.reservations:
        for i, res in enumerate(st.session_state.reservations):
            st.markdown(f"### Réservation {i+1}")
            cols = st.columns([2,1,1])
            with cols[0]:
                res["name"] = st.text_input("Nom", value=res.get("name", ""), key=f"r_name_{i}")
            with cols[1]:
                res["time"] = st.text_input("Heure", value=res.get("time", ""), key=f"r_time_{i}")
            with cols[2]:
                res["pax"] = st.text_input("Pax", value=res.get("pax", ""), key=f"r_pax_{i}")
            res["note"] = st.text_area("Note sur la réservation", value=res.get("note", ""), key=f"r_note_{i}")

            st.write("Plats détectés (corrigez si besoin):")
            to_del = []
            for j, it in enumerate(res.get("items", [])):
                c1, c2, c3 = st.columns([6,2,1])
                with c1:
                    it["name"] = st.text_input("Plat", value=it.get("name", ""), key=f"it_name_{i}_{j}")
                with c2:
                    it["qty"] = int(st.number_input("Qté", value=int(it.get("qty", 1)), min_value=0, max_value=999, key=f"it_qty_{i}_{j}"))
                with c3:
                    if st.button("Suppr", key=f"it_del_{i}_{j}"):
                        to_del.append(j)
            for j in sorted(to_del, reverse=True):
                del res["items"][j]
            if st.button("+ Ajouter un plat", key=f"add_item_{i}"):
                res["items"].append({"section": "", "name": "", "qty": 1, "score": 0, "original": ""})

with export_tab:
    st.subheader("Générer la fiche cuisine PDF")
    title = st.text_input("Titre", value="Fiche Cuisine")
    date_label = st.text_input("Date", value="")
    service_label = st.text_input("Service", value="")
    if st.button("Générer"):
        # Aggregate totals across reservations
        all_items: List[Dict] = []
        for res in st.session_state.reservations:
            all_items.extend(res.get("items", []))
        totals = matcher.aggregate(all_items)
        pdf_bytes = pdf_gen.generate_fiche_pdf(title, date_label, service_label, st.session_state.reservations, totals)
        st.download_button("Télécharger la fiche.pdf", data=pdf_bytes, file_name="fiche_cuisine.pdf", mime="application/pdf")
