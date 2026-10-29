"""
config.py - Central configuration for the Student Placement & Career Analytics System.

All secrets (database password, Flask secret key) are read from environment
variables. During development they are loaded from a local `.env` file
(copy `.env.example` to `.env` and fill in your own values).
"""
import os

from dotenv import load_dotenv

# Load variables from the .env file that sits next to this file (if present).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    # ---- Flask ----
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret-key")
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # login session lasts 8 hours
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # ---- MySQL ----
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "placement_analytics")

    # ---- Application settings ----
    # The batch whose placement season is still running (shown as "Ongoing").
    ONGOING_BATCH = int(os.getenv("ONGOING_BATCH", "2025"))
    STUDENTS_PER_PAGE = int(os.getenv("STUDENTS_PER_PAGE", "15"))
    APP_NAME = "Student Placement Analytics"

    # Salary bands used by BOTH the Flask dashboard and Tableau (see schema.sql view).
    CTC_BANDS = ["0-10 LPA", "10-20 LPA", "20-30 LPA", "30+ LPA"]

    # Folder where CSV reports are written by `python analytics.py --export`.
    REPORTS_DIR = os.path.join(BASE_DIR, "reports_output")
