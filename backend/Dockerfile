# 1. Imagen oficial ligera
FROM python:3.11-slim

# 2. Variables de entorno para logs limpios
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# 4. Instalación de librerías Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar el código del proyecto
COPY . .

# Generation includes external requests. Keep the worker alive while Cloud Run
# enforces the request timeout; one worker also respects Nominatim's local limiter.
CMD exec gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT --timeout 300
