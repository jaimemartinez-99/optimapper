# 1. Imagen oficial ligera
FROM python:3.11-slim

# 2. Variables de entorno para logs limpios
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# 3. Dependencias del sistema (libgomp1 es clave para K-Means/scikit-learn)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 4. Instalación de librerías Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar el código del proyecto
COPY . .

# 6. COMANDO DE EJECUCIÓN (El cambio principal)
# Usamos Gunicorn con el worker de Uvicorn para máxima estabilidad en Cloud Run.
# Asegúrate de tener 'gunicorn' en tu requirements.txt
CMD gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT