FROM python:3.12-slim

WORKDIR /app

# tesseract-ocr : moteur OCR utilisé par pytesseract (app/anpr_engine.py).
# libgl1 / libglib2.0-0 : dépendances runtime d'OpenCV (même en version
# "headless", certains modules de décodage d'image en ont besoin).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY migrations ./migrations

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
