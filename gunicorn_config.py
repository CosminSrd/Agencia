import multiprocessing
import os

# Gunicorn config variables
# Reducido a 4 workers para evitar sobrecarga de DB
workers = 4  # Era: multiprocessing.cpu_count() * 2 + 1
bind = "0.0.0.0:8000"
keepalive = 120
errorlog = "-"
accesslog = "-"
loglevel = "info"
worker_class = "gthread"
threads = 4  # Aumentado de 2 a 4
timeout = 120

# Environment variables
raw_env = [
    "FLASK_ENV=production",
    "PYTHONUNBUFFERED=true",
]
