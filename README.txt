# SkillSwap — Skill Exchange Platform

## Overview
SkillSwap is a web application designed to help users exchange skills.
Users can offer skills they know, request skills they want to learn,
and connect with other users for skill-exchange sessions.

## Technology Stack
- Frontend: HTML, CSS, JavaScript
- Backend: Python and Flask
- Database: Oracle Database
- Database connectivity: Python oracledb

## Main Features
- User and skill management
- Skill offerings and skill requests
- User preferences and availability
- Skill matching between users
- Session scheduling and tracking
- Reviews and ratings

## Project Structure
- backend/app.py — Flask application and API routes
- backend/database.py — Oracle database connectivity
- backend/requirements.txt — Python dependencies
- backend/check_setup.py — Setup and structural checks
- backend/frontend/ — HTML, CSS and JavaScript frontend
- database/01_create_tables.sql — Table definitions
- database/02_insert_data.sql — Sample data
- database/03_queries.sql — SQL queries
- database/04_views.sql — Database views
- database/05_procedures.sql — Stored procedures
- database/06_triggers.sql — Database triggers

## Setup

### 1. Configure Oracle Database
Ensure Oracle Database is running and the SkillSwap schema
and tables have been created using the supplied SQL scripts.

Check backend/database.py for the expected connection settings.
Do not commit passwords, API keys or other credentials.

### 2. Install Python Dependencies
From the project root, run:

    cd backend
    python3 -m pip install -r requirements.txt

### 3. Run Setup Checks

    python3 check_setup.py

### 4. Start the Application

    python3 app.py

Open http://127.0.0.1:5000 in your browser.

If the application provides the health endpoint, check:
http://127.0.0.1:5000/api/health

## Notes
- Oracle Database must be configured and accessible for database
  operations to work.
- The SQL scripts are included in the database directory.
- The .venv directory, Python cache files, local environment files,
  and macOS .DS_Store files are excluded through .gitignore.
