# Project Setup for UFS Back End

## Introduction

This guide will walk you through how to clone the project, set up the environment, install necessary dependencies, configure PostgreSQL, and run the server.

---

## 1. Clone the Project

```bash
git clone https://github.com/vnb-it-organisation/repository-ufs_back_end.git
cd repository-ufs_back_end
```

---

## 2. Set Up a Virtual Environment

1. **Create a virtual environment** to keep dependencies isolated:

   #### For Windows:

   ```bash
   python -m venv venv
   ```
   ### pip install --upgrade pip setuptools wheel:

   #### For macOS/Linux:

   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment**:

   #### For Windows:

   ```bash
   venv\Scripts\activate
   ```

   #### For macOS/Linux:

   ```bash
   source venv/bin/activate
   ```

---

## 3. Install Dependencies

1. **Install all required packages** by running this command:

   ```bash
   pip install -r requirements.txt
   ```

---

## 4. Configure PostgreSQL Database

1. **Create a database** and user:

   - Open the PostgreSQL terminal:

     ```bash
     psql -U postgres
     ```

   - Run these commands in the PostgreSQL terminal:

     ```sql
     CREATE DATABASE ufs_db;
     ```

2. **CREATE AND Update the `.env` file**:

   Inside the Project_UFS folder, create a .env file by copying the variables from .env.example.

   Below is a section of the variables you may need to modify in the .env file:

   ```plaintext
    DB_NAME=ufs_db
    DB_USER=postgres
    DB_PASSWORD=password   # Change this to ur own password
    DB_HOST=localhost
    DB_PORT=5432
   ```

---

## 5. Run the Server

1. **Apply migrations** to set up the database schema:

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Start the Django development server**:

   ```bash
   python manage.py runserver
   ```

3. **Access the project** by going to `http://127.0.0.1:8000/swagger` in your browser.

# Wolof-Sign Django Backend

## Configuration des fichiers média en production

### Important pour le déploiement sur Railway

Lorsque vous déployez sur Railway ou tout autre service avec des conteneurs éphémères, gardez à l'esprit que les fichiers téléchargés dans le répertoire `media/` ne seront pas persistants. Après un redémarrage du conteneur ou un nouveau déploiement, ces fichiers seront perdus.

### Solutions recommandées pour la production:

1. **Utiliser un service de stockage externe** comme AWS S3, Google Cloud Storage, ou similaire:
   - Installez `django-storages` et `boto3` pour AWS S3:
     ```
     pip install django-storages boto3
     ```
   - Ajoutez `storages` à `INSTALLED_APPS` 
   - Configurez AWS S3 dans `.env`:
     ```
     AWS_ACCESS_KEY_ID=votre_cle_acces
     AWS_SECRET_ACCESS_KEY=votre_cle_secrete
     AWS_STORAGE_BUCKET_NAME=nom_de_votre_bucket
     ```
   - Le code pour utiliser S3 est déjà préparé dans `settings.py`, il suffit de décommenter et configurer.

2. **Alternative**: PostgreSQL Large Objects
   - Vous pouvez stocker de petits fichiers directement dans la base de données PostgreSQL
   - Cependant, cela n'est pas recommandé pour les fichiers volumineux ou nombreux

### Configuration actuelle

Le backend est configuré pour servir les fichiers média via l'URL `/media/` en environnement de développement et en production.

Pour les fichiers PDF spécifiquement, un middleware personnalisé (`MediaFilesMiddleware`) a été ajouté pour configurer correctement les en-têtes CORS et le type de contenu.
