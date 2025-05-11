# Utiliser Debian comme image de base
FROM debian:latest

# Mettre à jour les paquets et installer les dépendances nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /app

# Copier requirements.txt avant le reste pour optimiser le cache Docker
COPY requirements.txt .

# Créer un environnement virtuel Python
RUN python3 -m venv /app/venv

# Activer l'environnement virtuel et installer les dépendances
RUN /app/venv/bin/pip install --upgrade pip && \
    /app/venv/bin/pip install -r requirements.txt

# Copier le contenu du projet dans le conteneur
COPY . .

# Rendre le script de démarrage exécutable
RUN echo '#!/bin/bash\n' \
         'source /app/venv/bin/activate\n' \
         'python3 manage.py makemigrations\n' \
         'python3 manage.py migrate\n' \
         'exec python3 manage.py runserver 0.0.0.0:8000\n' \
         > /app/start.sh && chmod +x /app/start.sh

# Exposer le port utilisé par Django
EXPOSE 8000

# Utiliser le script de démarrage comme point d'entrée
CMD ["/bin/bash", "/app/start.sh"]
