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
