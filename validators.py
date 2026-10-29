"""
validators.py - Server-side validation for the student form.

The browser also checks fields (HTML5 'required', 'min', 'max'), but the
server ALWAYS re-checks because browser checks can be bypassed.
"""
import re
from datetime import date, datetime

STUDENT_ID_RE = re.compile(r"^[A-Za-z0-9]{3,12}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
STATUSES = ["Placed", "Offer Pending", "Not Placed"]


def validate_student_form(form, dept_codes, company_ids, skill_ids, is_new=True):
    """
    Check the submitted form.
    Returns (data, errors): `data` holds cleaned values, `errors` is a list of messages.
    """
    errors = []
    data = {
        "student_id": form.get("student_id", "").strip().upper(),
        "student_name": " ".join(form.get("student_name", "").split()),
        "department": form.get("department", "").strip(),
        "email": form.get("email", "").strip().lower(),
        "eligible": 1 if form.get("eligible") == "1" else 0,
        "placement_status": form.get("placement_status", "Not Placed"),
        "company_id": None, "package_lpa": None, "placement_date": None, "skills": [],
    }

    if is_new and not STUDENT_ID_RE.match(data["student_id"]):
        errors.append("Student ID must be 3-12 letters or digits (for example 25CSE041).")
    if not NAME_RE.match(data["student_name"]):
        errors.append("Student name must start with a letter and contain only letters, spaces, . ' or -.")
    if data["department"] not in dept_codes:
        errors.append("Please choose a valid department.")
    if not EMAIL_RE.match(data["email"]) or len(data["email"]) > 120:
        errors.append("Please enter a valid email address.")

    try:
        data["batch_year"] = int(form.get("batch_year", ""))
        if not 2000 <= data["batch_year"] <= 2100:
            raise ValueError
    except ValueError:
        data["batch_year"] = None
        errors.append("Batch year must be a 4-digit year between 2000 and 2100.")

    try:
        data["cgpa"] = round(float(form.get("cgpa", "")), 2)
        if not 0 <= data["cgpa"] <= 10:
            raise ValueError
    except ValueError:
        data["cgpa"] = None
        errors.append("CGPA must be a number between 0 and 10.")

    for raw in form.getlist("skills"):
        if raw.isdigit() and int(raw) in skill_ids:
            data["skills"].append(int(raw))
    data["skills"] = sorted(set(data["skills"]))      # remove duplicates

    status = data["placement_status"]
    if status not in STATUSES:
        errors.append("Invalid placement status.")
    elif status != "Not Placed":
        if not data["eligible"]:
            errors.append("A student who is not eligible for placement cannot be marked as placed.")
        cid = form.get("company_id", "")
        if cid.isdigit() and int(cid) in company_ids:
            data["company_id"] = int(cid)
        else:
            errors.append("Please choose the recruiting company.")
        try:
            data["package_lpa"] = round(float(form.get("package_lpa", "")), 2)
            if not 0.5 <= data["package_lpa"] <= 200:
                raise ValueError
        except ValueError:
            errors.append("Package must be between 0.5 and 200 LPA.")
        try:
            data["placement_date"] = datetime.strptime(form.get("placement_date", ""), "%Y-%m-%d").date()
            if data["placement_date"] > date.today():
                errors.append("Placement date cannot be in the future.")
        except ValueError:
            errors.append("Please enter a valid placement date.")

    return data, errors
