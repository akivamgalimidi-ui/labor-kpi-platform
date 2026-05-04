# Avir Labor KPI Analytics

This project has been re-architected from a local SQLite proof-of-concept into a production-grade, Decoupled Architecture powered by a **FastAPI/Supabase** backend and a **React/Tailwind** frontend.

## Directory Structure to Upload to GitHub

You should upload the following folders and files to your GitHub repository:

```text
/backend/
  ├── main.py                  # The new FastAPI server replacing the old Flask app
  ├── supabase_client.py       # Client for connecting to Supabase over REST
  ├── database.py              # Refactored DB handler for Supabase
  ├── parser.py                # Excel parsing logic
  ├── kpi_engine.py            # Financial and KPI calculations
  ├── export.py                # Excel export logic
  └── requirements.txt         # Python dependencies

/frontend/
  └── index.html               # Standalone React + Tailwind + Recharts dashboard

/supabase/
  └── migrations/
      └── 20260504_initial_schema.sql  # The entire Postgres database schema
      
.gitignore                     # Prevents junk files (like pycache and Excel files) from uploading
README.md                      # This file!
```

> **Note:** The old `app/` folder has been renamed to `.legacy_app/` so you do not accidentally upload the outdated SQLite code to GitHub. `.legacy_app/` is ignored by `.gitignore`.

## Getting Started

### 1. Initialize the Database
Open the `supabase/migrations/20260504_initial_schema.sql` file, copy all the SQL, and paste it into your Supabase SQL Editor. Run the query to create all 23 normalized tables.

### 2. Run the Backend API
You have all the Python requirements installed. Run the FastAPI server natively:
```powershell
python backend/main.py
```
This will start the backend engine on `http://localhost:8000`.

### 3. Open the Frontend
Since you do not have Node.js installed locally, the React app was built to run natively in your browser. Double click `frontend/index.html` to open it in Chrome/Edge. It will automatically talk to the backend running on port 8000!
