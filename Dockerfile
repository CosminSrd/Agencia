# Usamos una versión ligera de Python sobre Linux (Debian)
FROM python:3.9-slim

# Evita que Python genere archivos .pyc y mejora los logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalamos dependencias del sistema necesarias para compilar cosas
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copiamos los requisitos e instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Puerto que expondremos
EXPOSE 4242

# Comando por defecto (Gunicorn en modo Producción)
# Pero ojo: En docker-compose lo sobrescribiremos para modo desarrollo
CMD ["gunicorn", "--bind", "0.0.0.0:4242", "app:app"]