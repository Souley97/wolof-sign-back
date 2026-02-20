# Déploiement du backend Wolof Sign sur VPS (sans Docker)

Guide pour déployer l’API Django sur un VPS (ex. LWS) avec Nginx, Gunicorn et PostgreSQL.

---

## Prérequis sur le VPS

- Accès root ou sudo
- Nginx déjà installé et actif (port 80 libre)
- Nom de domaine pointant vers l’IP du VPS (ex. `apisign.wolofdigital.com`)

---

## 1. Installer les paquets système

```bash
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev python3-pip build-essential libpq-dev postgresql-client git
```

`libpq-dev` et `python3.13-dev` sont nécessaires pour compiler **psycopg2-binary** si aucun wheel préconstruit n’est disponible pour ta plateforme.

---

## 2. Créer l’utilisateur applicatif (recommandé)

```bash
sudo adduser --disabled-password --gecos '' wolofsign
sudo usermod -aG www-data wolofsign
```

---

## 3. PostgreSQL : créer la base et l’utilisateur

```bash
sudo -u postgres psql
```

Dans psql :

```sql
CREATE DATABASE wolofsign;
CREATE USER wolofsign WITH PASSWORD 'wolof@123';
ALTER ROLE wolofsign SET client_encoding TO 'utf8';
ALTER ROLE wolofsign SET default_transaction_isolation TO 'read committed';
ALTER ROLE wolofsign SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE wolofsign TO wolofsign;
\c wolofsign
GRANT ALL ON SCHEMA public TO wolofsign;
\q
```

---

## 4. Cloner le projet et préparer l’environnement

```bash
# Exemple : cloner dans /var/www (ou /home/wolofsign)
sudo mkdir -p /var/www
sudo chown wolofsign:wolofsign /var/www
sudo -u wolofsign git clone https://github.com/Souley97/wolof-sign-back.git /var/www/wolof-sign-back
cd /var/www/wolof-sign-back
```

Créer le venv et installer les dépendances :

```bash
sudo chown -R wolofsign:wolofsign /var/www/wolof-sign-back
cd /var/www/wolof-sign-back
sudo -u wolofsign python3 -m venv venv
sudo -u wolofsign ./venv/bin/pip install --upgrade pip
sudo -u wolofsign ./venv/bin/pip install -r requirements.txt gunicorn
```

---

## 5. Fichier `.env` en production

Créer ou éditer `.env` à la racine du projet (ex. `/var/www/wolof-sign-back/.env`) :

```bash
sudo -u wolofsign nano /var/www/wolof-sign-back/.env
```

Exemple (à adapter avec vos valeurs) :

```env
DJANGO_SECRET_KEY=une-cle-secrete-tres-longue-et-aleatoire
DJANGO_DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,apisign.wolofdigital.com,sign.wolofdigital.com

# Base PostgreSQL sur le VPS
DATABASE_URL=postgresql://wolofsign:VOTRE_MOT_DE_PASSE_FORT@localhost:5432/wolofsign

# CORS et URLs
CORS_ALLOWED_ORIGINS=https://sign.wolofdigital.com,https://apisign.wolofdigital.com
FRONTEND_URL=https://sign.wolofdigital.com
SITE_URL=https://apisign.wolofdigital.com

# Chiffrement signatures (générer avec: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
SIGNATURE_ENCRYPTION_KEY=VOTRE_CLE_FERNET

# Email (SMTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=votre-email@gmail.com
EMAIL_HOST_PASSWORD=mot-de-passe-application
DEFAULT_FROM_EMAIL=votre-email@gmail.com

# Stripe / PayDunya (si utilisé)
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
PAYDUNYA_MASTER_KEY=...
PAYDUNYA_PRIVATE_KEY=...
PAYDUNYA_PUBLIC_KEY=...
PAYDUNYA_TOKEN=...
```

Ne pas commiter le `.env` (il doit être dans `.gitignore`).

---

## 6. Migrations et fichiers statiques

```bash
cd /var/www/wolof-sign-back
sudo -u wolofsign ./venv/bin/python manage.py migrate
sudo -u wolofsign ./venv/bin/python manage.py collectstatic --noinput
sudo -u wolofsign mkdir -p media staticfiles logs
```

---

## 7. Tester Gunicorn

```bash
cd /var/www/wolof-sign-back
sudo -u wolofsign ./venv/bin/gunicorn core.wsgi:application --bind 127.0.0.1:8000 --workers 2
```

Depuis un autre terminal (ou depuis la machine) : `curl http://127.0.0.1:8000/api/docs/`. Arrêter avec Ctrl+C.

---

## 8. Service systemd pour Gunicorn

Copier le fichier fourni :

```bash
sudo cp /var/www/wolof-sign-back/deploy/gunicorn.service /etc/systemd/system/wolofsign.service
```

Éditer si besoin le chemin et l’utilisateur :

```bash
sudo nano /etc/systemd/system/wolofsign.service
```

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable wolofsign
sudo systemctl start wolofsign
sudo systemctl status wolofsign
```

---

## 9. Nginx (reverse proxy vers Gunicorn)

Créer un vhost (remplacer `apisign.wolofdigital.com` par votre domaine API) :

```bash
sudo cp /var/www/wolof-sign-back/deploy/nginx.wolofsign.conf /etc/nginx/sites-available/wolofsign
sudo ln -s /etc/nginx/sites-available/wolofsign /etc/nginx/sites-enabled/
```

Vérifier la config et recharger Nginx :

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Pour le HTTPS (Let’s Encrypt) :

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d apisign.wolofdigital.com
```

---

## 10. Droits et sécurité

```bash
sudo chown -R wolofsign:www-data /var/www/wolof-sign-back
sudo chmod -R 750 /var/www/wolof-sign-back
sudo chmod 640 /var/www/wolof-sign-back/.env
sudo chmod -R 770 /var/www/wolof-sign-back/media
sudo chmod -R 755 /var/www/wolof-sign-back/staticfiles
```

---

## Commandes utiles

| Action | Commande |
|--------|----------|
| Logs Gunicorn | `sudo journalctl -u wolofsign -f` |
| Redémarrer l’API | `sudo systemctl restart wolofsign` |
| Logs Nginx | `sudo tail -f /var/log/nginx/error.log` |
| Migrations après mise à jour | `cd /var/www/wolof-sign-back && sudo -u wolofsign ./venv/bin/python manage.py migrate` |
| Collectstatic après mise à jour | `sudo -u wolofsign ./venv/bin/python manage.py collectstatic --noinput` |

---

## Dépannage

- **Erreur de build psycopg2-binary** : Installer les paquets de développement puis réessayer : `sudo apt install -y libpq-dev python3.13-dev`, puis `./venv/bin/pip install -r requirements.txt`.
- **502 Bad Gateway** : Gunicorn ne tourne pas ou pas sur 127.0.0.1:8000 → `systemctl status wolofsign`, vérifier le `--bind` dans le service.
- **403 / CORS** : Vérifier `CORS_ALLOWED_ORIGINS` et `ALLOWED_HOSTS` dans `.env`, et les en-têtes dans la config Nginx.
- **Static/Media 404** : Vérifier les `alias` dans Nginx (chemins vers `staticfiles` et `media`).
- **Base de données** : Vérifier `DATABASE_URL`, que PostgreSQL écoute sur localhost et que l’utilisateur a bien les droits sur la base `wolofsign`.
