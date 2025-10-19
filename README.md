# Fiche Cuisine App (FR/NL)

Application Streamlit pour extraire les plats à partir des captures d'écran de réservations (texte dans "Note sur la réservation") et générer automatiquement une fiche cuisine PDF. L'app apprend votre carte à partir de vos menus PDF (français et néerlandais/Belgique) pour reconnaître les plats, desserts, formules, etc.

## Installation (Windows)

1. Installer Python 3.10+
2. Installer Tesseract OCR (obligatoire pour l'OCR FR/NL)
   - Téléchargement: https://github.com/UB-Mannheim/tesseract/wiki
   - Pendant l'installation, cocher les langues: French (fra) et Dutch (nld)
   - Notez le chemin d'installation (ex: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
3. (Optionnel pour menus PDF scannés) Installer Poppler for Windows
   - Téléchargement: https://github.com/oschwartz10612/poppler-windows/releases/
   - Ajoutez le dossier `poppler-xx\Library\bin` au `PATH` si vous avez des menus scannés/images
4. Ouvrir un terminal dans le dossier du projet et installer les dépendances:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

5. Si Tesseract n'est pas dans le PATH, créez une variable d'environnement avant de lancer l'app:

```
set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Lancer l'application

```
streamlit run fiche_cuisine_app/app.py
```

## Déploiement sur Railway (Docker)

Cette app est prête pour Railway via le `Dockerfile` fourni.

1. Créez un dépôt Git (GitHub/GitLab) contenant ce dossier.
2. Vérifiez les fichiers:
   - `Dockerfile` (installe Tesseract FR/NL et Poppler, et lance Streamlit sur `$PORT`)
   - `.dockerignore`
   - `.streamlit/config.toml`
3. Sur Railway:
   - Créez un nouveau projet → Déployez depuis votre repo ("Deploy from GitHub").
   - Railway détectera le `Dockerfile` et construira l'image.
   - Aucune variable d'env obligatoire. `$PORT` est injecté par Railway.
4. Après le déploiement:
   - Ouvrez l'URL Railway et utilisez l'app directement.

Notes:
- Le conteneur installe `tesseract-ocr`, `tesseract-ocr-fra`, `tesseract-ocr-nld` et `poppler-utils`. Vous n'avez rien à configurer.
- Si vos menus sont très lourds, prévoyez d'augmenter la RAM/CPU du service Railway.
- Streamlit est démarré avec `--server.address=0.0.0.0` et `--server.port=$PORT` via la commande `CMD` du Dockerfile.

## Utilisation

- Onglet 1: Charger vos menus en PDF (FR/NL). L'app construit un lexique de plats par sections (Entrées/Plats/Desserts/Formules). Vous pouvez revoir/éditer les entrées.
- Onglet 2: Importer une ou plusieurs captures d'écran de réservations. L'OCR récupère la zone "Note sur la réservation". L'app propose des correspondances (avec quantités). Vous pouvez corriger/éditer.
- Générer: Télécharger la fiche cuisine PDF A4 avec résumé par service/heure et total par plat.

## Limitations connues

- Les PDF scannés sans texte: l'app essaie l'OCR, mais la qualité dépend des images.
- Les fautes de frappe dans les notes: l'app utilise un appariement flou, mais un contrôle manuel reste proposé dans l'UI.
- Langues supportées: FR et NL (Belgique). Vous pouvez enrichir le lexique via vos menus.

## Structure

```
fiche_cuisine_app/
  app.py            # UI Streamlit
  ocr.py            # OCR images (Tesseract) avec pré-traitement
  menu_parser.py    # Extraction de texte des PDF, détection des sections FR/NL
  matcher.py        # Fuzzy matching et extraction des quantités
  pdf_gen.py        # Génération du PDF de fiche cuisine (ReportLab)
```

## Astuces de précision

- Importez vos menus officiels (FR et NL) pour remplir le lexique.
- Ajoutez des variantes orthographiques/fautes fréquentes dans les sections correspondantes.
- Si une note contient plusieurs plats sur une ligne, séparez par `,` ou `;` dans l'éditeur pour une meilleure détection.
