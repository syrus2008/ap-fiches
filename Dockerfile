# Railway-ready Dockerfile for Streamlit + Tesseract (FR/NL) + Poppler
FROM python:3.10-slim

# System deps: tesseract (with FR/NL), poppler-utils for pdf2image OCR fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-nld \
    poppler-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy dependency spec first for caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY fiche_cuisine_app ./fiche_cuisine_app
COPY README.md ./README.md

# Expose default Streamlit port (Railway will map dynamically)
EXPOSE 8501

# Streamlit will be run on $PORT with 0.0.0.0 binding for Railway
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

CMD ["bash", "-lc", "streamlit run fiche_cuisine_app/app.py --server.port=$PORT --server.address=0.0.0.0"]
