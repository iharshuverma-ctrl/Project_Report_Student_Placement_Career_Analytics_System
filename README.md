# Student Placement & Career Analytics System

A Business Analytics mini project built with **Python (Flask), MySQL, Pandas/NumPy, Chart.js, Bootstrap 5 and Tableau**.
It tracks campus placements, salary packages (CTC), recruiting companies, department performance and student skills.

> **Sample data notice** — `seed_data.py` generates **fictional** students and companies (fixed random seed 42).
> These figures are for demonstration only and are **not** real placement results of Chandigarh University or any other institution.

---

## Features

| Module | What it does |
|---|---|
| Dashboard | 4 KPI cards (total placements, average CTC, highest CTC, companies) with previous-batch comparison; 5 charts (monthly stacked bar, CTC distribution, category doughnut, department CTC comparison, top 10 recruiters). Batch dropdown reloads data from a JSON API without refreshing the page. |
| Student Records | Table with search (name / ID), filters (department, batch, status), pagination, add / edit / delete with validation. |
| Company Analytics | Hires, average & highest package, batches and departments per company; filters for batch, department and category; comparison chart; add-company form. |
| Department Analytics | Total, eligible, placed students, placement %, average / median / highest package. Departments are configurable (Settings). |
| Skills Analytics | Most common skills, placement rate by skill and certification, recruiter skill demand, department × skill matrix (descriptive only). |
| Reports | 8 CSV downloads (incl. the Tableau dataset) + data-quality report. |
| Settings | DB status, change password, add / rename / deactivate departments. |
| Security | Login with hashed passwords, admin / viewer roles, CSRF tokens on all forms, parameterized SQL, credentials in `.env`. |
| UI | Fixed sidebar, breadcrumb, light / dark theme toggle, responsive down to phone width. |

## Project structure

```
placement_analytics/
├── app.py                  Flask app factory, login guard, CSRF, error pages
├── config.py               Settings read from .env
├── database.py             MySQL connection pool + parameterized query helpers
├── analytics.py            Pandas / NumPy cleaning and analysis (no Flask code)
├── validators.py           Server-side validation of the student form
├── schema.sql              Database, 9 tables, 3 shared views
├── seed_data.py            Reproducible fictional sample data
├── requirements.txt
├── .env.example
├── routes/                 auth, dashboard, students, companies, departments, skills, reports, settings
├── templates/              base layout + one template per page
├── static/css/style.css    Theme (light/dark) and layout
├── static/js/              app.js (theme, sidebar), charts.js (Chart.js helpers), dashboard.js
├── static/images/logo.svg
├── tests/test_app.py       28 automated tests (pytest)
├── tableau/placement_dashboard_instructions.md
└── docs/                   development guide, test cases, report outline, screenshots, viva Q&A
```

## Quick start

Prerequisites: **Python 3.10+**, **MySQL Server 8.0+** (with MySQL Workbench), VS Code, internet access in the browser (Bootstrap, Chart.js and icons load from a CDN).

```bash
# 1. open a terminal in the project folder
cd placement_analytics

# 2. virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # macOS / Linux

# 3. dependencies
pip install -r requirements.txt

# 4. database + tables + views   (enter your MySQL root password)
mysql -u root -p < schema.sql
#    (or open schema.sql in MySQL Workbench and press the ⚡ Execute button)

# 5. configuration
copy .env.example .env           # Windows   (cp on macOS/Linux)
#    edit .env -> DB_USER, DB_PASSWORD, SECRET_KEY

# 6. sample data
python seed_data.py

# 7. check the connection
python database.py

# 8. run
python app.py
```

Open **http://127.0.0.1:5000** and log in:

| Username | Password | Can do |
|---|---|---|
| `admin` | `admin123` | everything (add / edit / delete) |
| `viewer` | `viewer123` | view only |

Change these passwords from **Settings** (or set `SEED_ADMIN_PASSWORD` / `SEED_VIEWER_PASSWORD` in `.env` before seeding).

### Optional: a dedicated MySQL user (recommended instead of root)

```sql
CREATE USER 'placement_user'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT ALL PRIVILEGES ON placement_analytics.* TO 'placement_user'@'localhost';
FLUSH PRIVILEGES;
```

Then use `DB_USER=placement_user` and that password in `.env`.

## Run the tests

```bash
python -m pytest -v
```

Expected: `28 passed`. The tests log in, check every page, compare the dashboard KPIs with direct SQL,
run the full add → edit → delete cycle for a temporary student `TEST9001`, check validation,
viewer permissions, CSRF protection, CSV export and SQL-injection safety.

## Useful commands

| Command | Purpose |
|---|---|
| `python database.py` | Test the MySQL connection and show row counts |
| `python analytics.py` | Print KPIs for each batch + data-quality report |
| `python analytics.py --export` | Write all CSV reports to `reports_output/` |
| `python seed_data.py` | Reset the database to the sample data |

## Troubleshooting

| Problem | Fix |
|---|---|
| `Could not connect to the MySQL database` | Start MySQL (Windows: *Services → MySQL80 → Start*), check `.env` values. |
| `Access denied for user` | Wrong `DB_USER`/`DB_PASSWORD`, or the user has no rights on `placement_analytics`. |
| `Table ... doesn't exist` | Run `schema.sql` first, then `seed_data.py`. |
| `'mysql' is not recognized` | Use MySQL Workbench to run `schema.sql`, or add `C:\Program Files\MySQL\MySQL Server 8.0\bin` to PATH. |
| Charts don't appear | The browser needs internet access for the CDN (Chart.js, Bootstrap). |
| `Your form session expired` | Reload the page; the CSRF token changes after logging in again. |
| `Port 5000 is in use` | `flask --app app run --port 5001` |

## Documentation

- `docs/DEVELOPMENT_GUIDE.md` — the 16 build steps with files, commands, expected output and checks
- `tableau/placement_dashboard_instructions.md` — Tableau connection, calculated fields, sheets, dashboard
- `docs/TEST_CASES.md` — manual + automated test cases with expected results
- `docs/PROJECT_REPORT_OUTLINE.md`, `docs/SCREENSHOTS_CHECKLIST.md`, `docs/VIVA_QA.md`
- `docs/screenshots/` — screenshots of the running app with the sample data
