"""
analytics.py - Data loading, cleaning and analysis with Pandas and NumPy.

This module contains NO Flask code. Route handlers call these functions and
send the results to templates or JSON endpoints. That keeps the analysis easy
to test and explain on its own.

Command-line use:
    python analytics.py               # print a quick summary of every batch
    python analytics.py --export      # write all summary reports to reports_output/*.csv
"""
import os
import sys

import numpy as np
import pandas as pd

from config import Config
from database import fetch_all, fetch_df

CTC_BANDS = Config.CTC_BANDS
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def r2(value):
    """Round to 2 decimals and convert NumPy types to plain Python (JSON-safe). NaN -> None."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, (np.floating, float)):
        return None if np.isnan(value) else round(float(value), 2)
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def pct_change(current, previous):
    """Percentage change from previous to current (None when it can't be calculated)."""
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / previous * 100, 1)


def ctc_band(package):
    """Same rule as the ctc_band column in vw_student_placements (schema.sql)."""
    if package is None or pd.isna(package):
        return None
    if package < 10:
        return "0-10 LPA"
    if package < 20:
        return "10-20 LPA"
    if package < 30:
        return "20-30 LPA"
    return "30+ LPA"


# ----------------------------------------------------------------------
# 1. LOAD data from MySQL
# ----------------------------------------------------------------------
def get_batches():
    """All batch years in the database, newest first."""
    return [row["batch_year"] for row in
            fetch_all("SELECT DISTINCT batch_year FROM students ORDER BY batch_year DESC")]


def get_departments(active_only=True):
    sql = "SELECT dept_code, dept_name, is_active FROM departments"
    if active_only:
        sql += " WHERE is_active = 1"
    return fetch_all(sql + " ORDER BY dept_code")


def get_company_categories():
    return [r["company_category"] for r in
            fetch_all("SELECT DISTINCT company_category FROM companies ORDER BY company_category")]


def load_student_data(batch=None, department=None):
    """One row per student from the shared view vw_student_placements, then cleaned."""
    sql = "SELECT * FROM vw_student_placements WHERE 1=1"
    params = []
    if batch:
        sql += " AND batch_year = %s"
        params.append(int(batch))
    if department:
        sql += " AND department = %s"
        params.append(department)
    df = fetch_df(sql, params)
    cleaned, _ = clean_placement_data(df)
    return cleaned


def load_skill_data(batch=None, department=None):
    """One row per (student, skill) from vw_student_skills."""
    sql = "SELECT * FROM vw_student_skills WHERE 1=1"
    params = []
    if batch:
        sql += " AND batch_year = %s"
        params.append(int(batch))
    if department:
        sql += " AND department = %s"
        params.append(department)
    df = fetch_df(sql, params)
    if not df.empty:
        df = df.drop_duplicates(subset=["student_id", "skill_id"])
        df["package_lpa"] = pd.to_numeric(df["package_lpa"], errors="coerce")
    return df


def load_company_demand(batch=None):
    sql = "SELECT * FROM vw_company_skill_demand WHERE 1=1"
    params = []
    if batch:
        sql += " AND batch_year = %s"
        params.append(int(batch))
    return fetch_df(sql, params)


# ----------------------------------------------------------------------
# 2. CLEAN data
# ----------------------------------------------------------------------
def clean_placement_data(df):
    """
    Clean the student/placement DataFrame and report what was fixed.

    - removes duplicate students (same student_id)
    - trims text and fills missing text values
    - converts numbers/dates to proper types
    - invalid CGPA (outside 0-10) becomes NaN
    - invalid package (<= 0 or > 200 LPA) is treated as missing, and the
      student is no longer counted as placed
    Returns (clean_df, report_dict).
    """
    report = {"rows_loaded": int(len(df)), "duplicates_removed": 0, "missing_values": {},
              "invalid_cgpa": 0, "invalid_package": 0, "rows_after_cleaning": int(len(df))}
    if df.empty:
        return df, report

    df = df.copy()
    report["missing_values"] = {col: int(n) for col, n in df[["student_name", "department", "cgpa", "email"]]
                                .isna().sum().items() if n}

    before = len(df)
    df = df.drop_duplicates(subset=["student_id"], keep="first")
    report["duplicates_removed"] = int(before - len(df))

    for col in ["student_name", "department", "company_name", "company_category"]:
        df[col] = df[col].astype("string").str.strip()
    df["student_name"] = df["student_name"].fillna("Unknown")

    df["cgpa"] = pd.to_numeric(df["cgpa"], errors="coerce")
    bad_cgpa = (df["cgpa"] < 0) | (df["cgpa"] > 10)
    report["invalid_cgpa"] = int(bad_cgpa.sum())
    df.loc[bad_cgpa, "cgpa"] = np.nan

    df["package_lpa"] = pd.to_numeric(df["package_lpa"], errors="coerce")
    bad_pkg = df["package_lpa"].notna() & ((df["package_lpa"] <= 0) | (df["package_lpa"] > 200))
    report["invalid_package"] = int(bad_pkg.sum())
    df.loc[bad_pkg, "package_lpa"] = np.nan
    df.loc[bad_pkg, "is_placed"] = 0

    df["placement_date"] = pd.to_datetime(df["placement_date"], errors="coerce")
    for col in ["is_placed", "is_eligible", "batch_year"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Recalculate the band in Python too (same rule as the SQL view)
    df["ctc_band"] = np.where(df["is_placed"] == 1, df["package_lpa"].map(ctc_band), None)

    report["rows_after_cleaning"] = int(len(df))
    return df, report


def data_quality_report():
    """Run the cleaning step on the full dataset and return its report."""
    df = fetch_df("SELECT * FROM vw_student_placements")
    _, report = clean_placement_data(df)
    return report


def placed_only(df):
    return df[df["is_placed"] == 1] if not df.empty else df


# ----------------------------------------------------------------------
# 3. ANALYSIS functions (each returns plain Python data, ready for JSON)
# ----------------------------------------------------------------------
def kpi_values(df):
    """Total placements, average / median / highest CTC and companies that hired."""
    placed = placed_only(df)
    if placed.empty:
        return {"total_placements": 0, "avg_ctc": None, "median_ctc": None,
                "highest_ctc": None, "companies": 0}
    return {
        "total_placements": int(len(placed)),
        "avg_ctc": r2(placed["package_lpa"].mean()),
        "median_ctc": r2(placed["package_lpa"].median()),
        "highest_ctc": r2(placed["package_lpa"].max()),
        "companies": int(placed["company_id"].nunique()),
    }


def kpi_summary(current_df, previous_df=None):
    """KPI cards: each value + previous batch value + % change."""
    cur = kpi_values(current_df)
    prev = kpi_values(previous_df) if previous_df is not None else None
    cards = {}
    for key in ["total_placements", "avg_ctc", "highest_ctc", "companies"]:
        previous_value = prev[key] if prev else None
        cards[key] = {
            "value": cur[key],
            "previous": previous_value,
            "change_pct": pct_change(cur[key], previous_value) if prev else None,
        }
    return cards


def monthly_placements(df):
    """Stacked bar data: placements per month, split by department (in season order)."""
    placed = placed_only(df).dropna(subset=["placement_date"])
    if placed.empty:
        return {"labels": [], "datasets": []}
    placed = placed.assign(period=placed["placement_date"].dt.to_period("M"))
    periods = pd.period_range(placed["period"].min(), placed["period"].max(), freq="M")
    table = (placed.pivot_table(index="period", columns="department", values="student_id",
                                aggfunc="count", fill_value=0)
             .reindex(periods, fill_value=0))
    labels = [f"{MONTH_NAMES[p.month - 1]} {str(p.year)[2:]}" for p in periods]
    datasets = [{"label": dept, "data": [int(v) for v in table[dept].tolist()]}
                for dept in sorted(table.columns)]
    return {"labels": labels, "datasets": datasets}


def ctc_distribution(df):
    """Number of placed students in each salary band."""
    placed = placed_only(df)
    counts = placed["ctc_band"].value_counts() if not placed.empty else pd.Series(dtype=int)
    return {"labels": CTC_BANDS, "data": [int(counts.get(band, 0)) for band in CTC_BANDS]}


def category_distribution(df):
    """Placements by company category (Product-Based, Service-Based, ...)."""
    placed = placed_only(df)
    if placed.empty:
        return {"labels": [], "data": [], "total": 0}
    counts = placed["company_category"].value_counts()
    return {"labels": counts.index.tolist(), "data": [int(v) for v in counts.values],
            "total": int(counts.sum())}


def department_summary(df):
    """Per-department table: total, eligible, placed, placement %, avg / median / highest CTC."""
    if df.empty:
        return []
    rows = []
    for dept, g in df.groupby("department"):
        placed = g[g["is_placed"] == 1]
        eligible = int(g["is_eligible"].sum())
        rows.append({
            "department": dept,
            "dept_name": g["dept_name"].iloc[0],
            "total_students": int(len(g)),
            "eligible_students": eligible,
            "placed_students": int(len(placed)),
            "placement_pct": round(len(placed) / eligible * 100, 1) if eligible else 0.0,
            "avg_ctc": r2(placed["package_lpa"].mean()) if not placed.empty else None,
            "median_ctc": r2(placed["package_lpa"].median()) if not placed.empty else None,
            "highest_ctc": r2(placed["package_lpa"].max()) if not placed.empty else None,
            "avg_cgpa": r2(g["cgpa"].mean()),
        })
    return sorted(rows, key=lambda r: (-r["placed_students"], r["department"]))


def department_chart(df):
    rows = department_summary(df)
    return {
        "labels": [r["department"] for r in rows],
        "avg": [r["avg_ctc"] or 0 for r in rows],
        "median": [r["median_ctc"] or 0 for r in rows],
        "placements": [r["placed_students"] for r in rows],
    }


def company_summary(df):
    """Per-company hiring table, sorted by number of students hired."""
    placed = placed_only(df)
    if placed.empty:
        return []
    grouped = placed.groupby(["company_id", "company_name", "industry", "company_category"])
    table = grouped.agg(hired=("student_id", "count"),
                        avg_ctc=("package_lpa", "mean"),
                        median_ctc=("package_lpa", "median"),
                        highest_ctc=("package_lpa", "max"),
                        batches=("batch_year", lambda s: ", ".join(str(b) for b in sorted(s.unique()))),
                        departments=("department", lambda s: ", ".join(sorted(s.unique()))))
    table = table.reset_index().sort_values(["hired", "avg_ctc"], ascending=[False, False])
    return [{
        "company_id": int(r.company_id), "company_name": r.company_name, "industry": r.industry,
        "company_category": r.company_category, "hired": int(r.hired), "avg_ctc": r2(r.avg_ctc),
        "median_ctc": r2(r.median_ctc), "highest_ctc": r2(r.highest_ctc),
        "batches": r.batches, "departments": r.departments,
    } for r in table.itertuples()]


def top_companies(df, n=10):
    rows = company_summary(df)[:n]
    return {"labels": [r["company_name"] for r in rows],
            "placements": [r["hired"] for r in rows],
            "avg_ctc": [r["avg_ctc"] for r in rows]}


def skill_summary(skill_df, student_df, skill_type="Technical"):
    """
    For each skill: how many students have it, how many of them were placed,
    their placement rate, and the difference from the overall placement rate.
    Only ELIGIBLE students are used for placement rates.
    DESCRIPTIVE ONLY - a higher rate does not prove the skill caused it.
    """
    if skill_df.empty or student_df.empty:
        return []
    eligible_students = student_df[student_df["is_eligible"] == 1]
    overall_rate = float(eligible_students["is_placed"].mean() * 100) if len(eligible_students) else 0.0
    s = skill_df[(skill_df["skill_type"] == skill_type)]
    rows = []
    for skill, g in s.groupby("skill_name"):
        elig = g[g["is_eligible"] == 1]
        placed = elig[elig["is_placed"] == 1]
        rate = len(placed) / len(elig) * 100 if len(elig) else 0
        rows.append({
            "skill_name": skill,
            "students": int(len(g)),
            "eligible": int(len(elig)),
            "placed": int(len(placed)),
            "placement_rate": round(rate, 1),
            "difference": round(rate - overall_rate, 1),
            "avg_ctc": r2(placed["package_lpa"].mean()) if len(placed) else None,
        })
    return sorted(rows, key=lambda r: -r["students"])


def overall_placement_rate(student_df):
    elig = student_df[student_df["is_eligible"] == 1] if not student_df.empty else student_df
    return round(elig["is_placed"].mean() * 100, 1) if len(elig) else 0.0


def company_skill_demand(demand_df, n=12):
    """How many companies asked for each skill."""
    if demand_df.empty:
        return []
    counts = (demand_df.drop_duplicates(subset=["company_id", "skill_name"])
              .groupby(["skill_name", "skill_type"])["company_id"].nunique()
              .reset_index(name="companies").sort_values("companies", ascending=False))
    return [{"skill_name": r.skill_name, "skill_type": r.skill_type, "companies": int(r.companies)}
            for r in counts.head(n).itertuples()]


def department_skill_matrix(skill_df, student_df, top_n=8):
    """% of each department's students who have each of the most common technical skills."""
    if skill_df.empty or student_df.empty:
        return {"skills": [], "rows": []}
    tech = skill_df[skill_df["skill_type"] == "Technical"]
    top_skills = tech["skill_name"].value_counts().head(top_n).index.tolist()
    dept_sizes = student_df.groupby("department")["student_id"].count()
    counts = (tech[tech["skill_name"].isin(top_skills)]
              .groupby(["department", "skill_name"])["student_id"].nunique().unstack(fill_value=0))
    rows = []
    for dept in sorted(dept_sizes.index):
        values = []
        for skill in top_skills:
            have = counts.loc[dept, skill] if (dept in counts.index and skill in counts.columns) else 0
            values.append(round(have / dept_sizes[dept] * 100, 0))
        rows.append({"department": dept, "values": [int(v) for v in values]})
    return {"skills": top_skills, "rows": rows}


def home_overview():
    """Small all-batch summary for the Home page."""
    df = load_student_data()
    if df.empty:
        return None
    placed = placed_only(df)
    return {
        "students": int(len(df)),
        "placed": int(len(placed)),
        "placement_pct": overall_placement_rate(df),
        "companies": int(placed["company_id"].nunique()) if not placed.empty else 0,
        "batches": int(df["batch_year"].nunique()),
        "departments": int(df["department"].nunique()),
        "is_sample": bool(df["is_sample"].astype(int).max() == 1),
    }


def dashboard_data(batch):
    """Everything the main dashboard needs for one batch (used by /api/dashboard)."""
    batches = get_batches()
    current = load_student_data(batch)
    previous_batch = next((b for b in sorted(batches, reverse=True) if b < int(batch)), None)
    previous = load_student_data(previous_batch) if previous_batch else None
    return {
        "batch": int(batch),
        "previous_batch": previous_batch,
        "is_ongoing": int(batch) == Config.ONGOING_BATCH,
        "is_sample_data": bool(not current.empty and current["is_sample"].astype(int).max() == 1),
        "has_data": bool(not current.empty),
        "kpis": kpi_summary(current, previous),
        "monthly": monthly_placements(current),
        "ctc_distribution": ctc_distribution(current),
        "categories": category_distribution(current),
        "departments": department_chart(current),
        "top_companies": top_companies(current, 10),
    }


# ----------------------------------------------------------------------
# 4. CSV REPORTS (used by the Reports page and the --export option)
# ----------------------------------------------------------------------
REPORTS = {
    "student_master": "Student master list (one row per student - also the Tableau dataset)",
    "department_summary": "Department-wise placement summary",
    "company_summary": "Company-wise recruitment summary",
    "ctc_distribution": "Salary band (CTC) distribution",
    "monthly_placements": "Month-wise placements by department",
    "skill_summary": "Technical skill vs placement rate (descriptive)",
    "certification_summary": "Certification vs placement rate (descriptive)",
    "data_quality": "Data cleaning / validation report",
}


def build_report(name, batch=None):
    """Return a DataFrame for the requested report name."""
    if name not in REPORTS:
        raise ValueError(f"Unknown report: {name}")
    if name == "data_quality":
        rep = data_quality_report()
        rep["missing_values"] = "; ".join(f"{k}={v}" for k, v in rep["missing_values"].items()) or "none"
        return pd.DataFrame([rep])

    df = load_student_data(batch)
    if name == "student_master":
        cols = ["student_id", "student_name", "department", "dept_name", "batch_year", "cgpa",
                "is_eligible", "student_status", "is_placed", "company_name", "company_category",
                "industry", "package_lpa", "ctc_band", "placement_date", "is_sample"]
        out = df[cols].copy() if not df.empty else pd.DataFrame(columns=cols)
        if not out.empty:
            out["placement_date"] = out["placement_date"].dt.strftime("%Y-%m-%d")
        return out
    if name == "department_summary":
        return pd.DataFrame(department_summary(df))
    if name == "company_summary":
        return pd.DataFrame(company_summary(df))
    if name == "ctc_distribution":
        d = ctc_distribution(df)
        return pd.DataFrame({"ctc_band": d["labels"], "placements": d["data"]})
    if name == "monthly_placements":
        m = monthly_placements(df)
        out = pd.DataFrame({"month": m["labels"]})
        for ds in m["datasets"]:
            out[ds["label"]] = ds["data"]
        return out
    skills = load_skill_data(batch)
    if name == "skill_summary":
        return pd.DataFrame(skill_summary(skills, df, "Technical"))
    return pd.DataFrame(skill_summary(skills, df, "Certification"))


def export_all_reports(folder=Config.REPORTS_DIR, batch=None):
    os.makedirs(folder, exist_ok=True)
    written = []
    for name in REPORTS:
        path = os.path.join(folder, f"{name}{'_' + str(batch) if batch else ''}.csv")
        build_report(name, batch).to_csv(path, index=False)
        written.append(path)
    return written


if __name__ == "__main__":
    if "--export" in sys.argv:
        for p in export_all_reports():
            print("Written:", p)
    else:
        for b in get_batches():
            k = kpi_values(load_student_data(b))
            print(f"Batch {b}: {k['total_placements']} placed | avg {k['avg_ctc']} LPA | "
                  f"median {k['median_ctc']} LPA | highest {k['highest_ctc']} LPA | {k['companies']} companies")
        print("Data quality:", data_quality_report())
