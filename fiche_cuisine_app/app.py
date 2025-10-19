import os
from typing import Dict, List
import streamlit as st
import sys
import logging

# Ensure project root is on sys.path so `fiche_cuisine_app` is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fiche_cuisine_app import ocr
from fiche_cuisine_app import menu_parser
from fiche_cuisine_app import matcher
from fiche_cuisine_app import pdf_gen
from fiche_cuisine_app import logging_utils

st.set_page_config(page_title="Fiche Cuisine", page_icon="🍽️", layout="wide")

if "lexicon" not in st.session_state:
    st.session_state.lexicon = {k: [] for k in menu_parser.SECTION_KEYWORDS.keys()}
if "reservations" not in st.session_state:
    st.session_state.reservations: List[Dict] = []
if "log_level" not in st.session_state:
    st.session_state.log_level = "INFO"

st.title("Fiche Cuisine (FR/NL)")

with st.expander("Configuration Tesseract", expanded=False):
    tess = st.text_input("Tesseract path (si non dans PATH)", value=os.environ.get("TESSERACT_CMD", ""))
    if st.button("Appliquer"):
        if tess and os.path.exists(tess):
            os.environ["TESSERACT_CMD"] = tess
            st.success("Chemin Tesseract enregistré. Relancez l'analyse si nécessaire.")
        else:
            st.warning("Chemin invalide.")

# Logging controls
with st.sidebar:
    st.markdown("### Journalisation")
    lvl = st.selectbox("Niveau de log", ["DEBUG", "INFO", "WARNING", "ERROR"], index=["DEBUG","INFO","WARNING","ERROR"].index(st.session_state.log_level))
    st.session_state.log_level = lvl
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    mem_handler = logging_utils.ensure_logging(level_map[lvl])
    if st.button("Vider les logs"):
        logging_utils.clear_logs()
    st.download_button("Télécharger les logs", data=logging_utils.get_logs_text().encode("utf-8"), file_name="fiche_cuisine_logs.txt")

menu_tab, notes_tab, export_tab = st.tabs(["1) Menus PDF → Lexique", "2) Réservations → Plats", "3) Générer PDF"]) 

with menu_tab:
    st.subheader("Importer vos menus (PDF FR/NL)")
    c1, c2 = st.columns(2)
    with c1:
        pdf_files = st.file_uploader("PDFs: Entrées / Plats / Desserts", type=["pdf"], accept_multiple_files=True, key="pdf_std")
    with c2:
        pdf_formules = st.file_uploader("PDFs: Formules / Menus (séparés)", type=["pdf"], accept_multiple_files=True, key="pdf_formules")

    c3, c4 = st.columns(2)
    with c3:
        force_ocr = st.checkbox("Forcer OCR (si texte non détecté)", value=False)
    with c4:
        forced_section = st.selectbox("Section forcée (pour PDF standard)", ["Aucune", "entries", "plats", "desserts"], index=0)

    if st.button("Construire/Mettre à jour le lexique") and (pdf_files or pdf_formules):
        logging.info("UI: Building lexicon from uploaded PDFs")
        combined = {k: list(st.session_state.lexicon.get(k, [])) for k in st.session_state.lexicon.keys()}
        import tempfile
        # Standard sections
        for up in (pdf_files or []):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
                tf.write(up.getbuffer())
                tmp_path = tf.name
            logging.debug(f"UI: Parsing standard menu PDF {up.name} at {tmp_path}")
            if force_ocr:
                text = menu_parser.extract_menu_text_force_ocr(tmp_path)
            else:
                text = menu_parser.extract_menu_text(tmp_path)
            fs = None if forced_section == "Aucune" else forced_section
            lex = menu_parser.build_lexicon_from_text(text, only_formules=False, forced_section=fs)
            # Auto fallback to OCR if nothing parsed and OCR not forced
            if not force_ocr and not any(lex.get(k) for k in ["entries", "plats", "desserts"]):
                logging.warning("UI: No items found via text extraction; retrying with OCR fallback")
                text = menu_parser.extract_menu_text_force_ocr(tmp_path)
                lex = menu_parser.build_lexicon_from_text(text, only_formules=False, forced_section=fs)
            combined = menu_parser.merge_lexicons(combined, lex)
        # Formules only
        for up in (pdf_formules or []):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
                tf.write(up.getbuffer())
                tmp_path = tf.name
            logging.debug(f"UI: Parsing formules PDF {up.name} at {tmp_path}")
            if force_ocr:
                text = menu_parser.extract_menu_text_force_ocr(tmp_path)
            else:
                text = menu_parser.extract_menu_text(tmp_path)
            lex_f = menu_parser.build_lexicon_from_text(text, only_formules=True)
            combined = menu_parser.merge_lexicons(combined, lex_f)
        st.session_state.lexicon = combined
        st.success("Lexique mis à jour.")
        logging.info("UI: Lexicon updated and stored in session")
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
        logging.info(f"UI: Analyzing {len(imgs)} uploaded image(s)")
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
        logging.info(f"UI: Detected {len(st.session_state.reservations)} reservation block(s)")
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
                logging.debug(f"UI: Deleted item index {j} from reservation {i}")
            if st.button("+ Ajouter un plat", key=f"add_item_{i}"):
                res["items"].append({"section": "", "name": "", "qty": 1, "score": 0, "original": ""})
                logging.debug(f"UI: Added empty item to reservation {i}")

with export_tab:
    st.subheader("Générer la fiche cuisine PDF")
    title = st.text_input("Titre", value="Fiche Cuisine")
    date_label = st.text_input("Date", value="")
    service_label = st.text_input("Service", value="")
    if st.button("Générer"):
        # Aggregate totals across reservations
        logging.info("UI: Generating fiche cuisine PDF")
        all_items: List[Dict] = []
        for res in st.session_state.reservations:
            all_items.extend(res.get("items", []))
        totals = matcher.aggregate(all_items)
        pdf_bytes = pdf_gen.generate_fiche_pdf(title, date_label, service_label, st.session_state.reservations, totals)
        st.download_button("Télécharger la fiche.pdf", data=pdf_bytes, file_name="fiche_cuisine.pdf", mime="application/pdf")
        logging.info("UI: PDF generated and ready for download")

# Show live logs in an expander at the bottom
with st.expander("Logs (live)", expanded=False):
    st.text_area("Logs", value=logging_utils.get_logs_text(), height=200)
