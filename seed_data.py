"""
seed_data.py - Generates REPRODUCIBLE, FICTIONAL sample placement data.

    python seed_data.py

* Every record created here is SAMPLE DATA (students.is_sample = 1, emails end in
  @example.edu, and all company names are invented). These numbers are NOT real
  placement results of Chandigarh University or of any other institution.
* A fixed random seed (42) means everyone who runs the script gets the same data.
* WARNING: the script first deletes all existing rows from every table.
"""
import os
import random
from datetime import date

from werkzeug.security import generate_password_hash

from database import DatabaseError, fetch_one, transaction

RANDOM_SEED = 42

# (code, full name, students per batch)
DEPARTMENTS = [
    ("CSE", "Computer Science and Engineering", 40),
    ("IT", "Information Technology", 28),
    ("ECE", "Electronics and Communication Engineering", 28),
    ("EE", "Electrical Engineering", 18),
    ("ME", "Mechanical Engineering", 18),
    ("MCA", "Master of Computer Applications", 20),
]
BATCHES = [2023, 2024, 2025]
ONGOING_BATCH = 2025          # placement season still running for this batch

# Fictional companies: (name, industry, category, typical CTC in LPA, hiring weight)
COMPANIES = [
    ("Nimbus Systems", "Cloud Software", "Product-Based", 24, 5),
    ("Quantix Labs", "AI & Analytics", "Product-Based", 28, 4),
    ("Vertexa Software", "SaaS", "Product-Based", 20, 5),
    ("Orbitron Technologies", "Semiconductors", "Product-Based", 22, 5),
    ("Lumen Fintech", "FinTech", "Product-Based", 18, 5),
    ("Cobalt Commerce", "E-commerce", "Product-Based", 16, 6),
    ("Helix HealthTech", "Health Technology", "Product-Based", 14, 5),
    ("Stratos Games", "Gaming", "Product-Based", 12, 4),
    ("Datacrest Cloud", "Data Platforms", "Product-Based", 19, 4),
    ("ZenPay Networks", "Payments", "Product-Based", 21, 4),
    ("Tecnova Solutions", "IT Services", "Service-Based", 5.0, 11),
    ("Pinnacle IT Services", "IT Services", "Service-Based", 4.2, 12),
    ("Coreline Digital", "Digital Services", "Service-Based", 6.5, 8),
    ("Sapphire Global Services", "IT Services", "Service-Based", 4.0, 10),
    ("Brightpath Technologies", "IT Services", "Service-Based", 7.0, 7),
    ("Infinity Infotech", "IT Services", "Service-Based", 4.6, 9),
    ("Meridian Analytics Consulting", "Analytics Consulting", "Consulting", 9, 4),
    ("Northstar Advisory", "Management Consulting", "Consulting", 12, 3),
    ("Keystone Business Consulting", "Business Consulting", "Consulting", 8, 3),
    ("Voltway Power Systems", "Power & Energy", "Core Engineering", 7, 4),
    ("Axiom Automotive", "Automotive", "Core Engineering", 8, 4),
    ("Tensile Infra Engineering", "Infrastructure", "Core Engineering", 6, 3),
    ("Circuitron Electronics", "Electronics", "Core Engineering", 9, 4),
    ("Gearwell Manufacturing", "Manufacturing", "Core Engineering", 6.5, 3),
    ("Signalwave Telecom", "Telecom", "Core Engineering", 10, 3),
]

# How likely each department is to be hired by each company category
DEPT_AFFINITY = {
    "CSE": {"Product-Based": 1.0, "Service-Based": 1.0, "Consulting": 0.6, "Core Engineering": 0.05},
    "IT": {"Product-Based": 0.8, "Service-Based": 1.0, "Consulting": 0.6, "Core Engineering": 0.05},
    "MCA": {"Product-Based": 0.5, "Service-Based": 1.0, "Consulting": 0.5, "Core Engineering": 0.0},
    "ECE": {"Product-Based": 0.5, "Service-Based": 0.8, "Consulting": 0.3, "Core Engineering": 0.8},
    "EE": {"Product-Based": 0.2, "Service-Based": 0.6, "Consulting": 0.3, "Core Engineering": 1.0},
    "ME": {"Product-Based": 0.1, "Service-Based": 0.4, "Consulting": 0.4, "Core Engineering": 1.0},
}
DEPT_BASE_PLACEMENT_RATE = {"CSE": 0.86, "IT": 0.82, "MCA": 0.74, "ECE": 0.74, "EE": 0.62, "ME": 0.56}

TECH_SKILLS = [
    "Python", "Java", "C++", "SQL", "JavaScript", "React", "Data Structures & Algorithms",
    "Machine Learning", "Cloud Computing", "Linux", "Data Analytics", "Embedded Systems",
    "VLSI Design", "MATLAB", "Power Systems", "AutoCAD",
]
CERTIFICATIONS = [
    "AWS Cloud Practitioner", "Google Data Analytics Certificate", "Oracle Java SE Certification",
    "Cisco CCNA", "Microsoft Azure Fundamentals", "NPTEL Certification", "Autodesk Certified User",
]

# Relative weight of each technical skill for each department
COMMON = {"Python": 6, "SQL": 5, "Java": 4, "C++": 4, "Data Analytics": 3, "Linux": 2}
DEPT_SKILL_WEIGHTS = {
    "CSE": {**COMMON, "Data Structures & Algorithms": 7, "JavaScript": 4, "React": 3,
            "Machine Learning": 4, "Cloud Computing": 3},
    "IT": {**COMMON, "Data Structures & Algorithms": 5, "JavaScript": 5, "React": 4,
           "Cloud Computing": 3, "Machine Learning": 2},
    "MCA": {**COMMON, "JavaScript": 5, "React": 3, "Data Structures & Algorithms": 3,
            "Cloud Computing": 2},
    "ECE": {**COMMON, "Embedded Systems": 6, "VLSI Design": 4, "MATLAB": 5,
            "Data Structures & Algorithms": 2, "Machine Learning": 2},
    "EE": {"Python": 3, "MATLAB": 6, "Power Systems": 6, "Embedded Systems": 3,
           "C++": 2, "SQL": 2, "Data Analytics": 2, "AutoCAD": 2},
    "ME": {"AutoCAD": 7, "MATLAB": 5, "Python": 3, "Data Analytics": 2, "SQL": 1, "C++": 1},
}
DEPT_CERT_WEIGHTS = {
    "CSE": {"AWS Cloud Practitioner": 4, "Microsoft Azure Fundamentals": 3,
            "Google Data Analytics Certificate": 2, "Oracle Java SE Certification": 3, "NPTEL Certification": 3},
    "IT": {"AWS Cloud Practitioner": 3, "Microsoft Azure Fundamentals": 3, "Cisco CCNA": 2,
           "Oracle Java SE Certification": 3, "NPTEL Certification": 3},
    "MCA": {"Oracle Java SE Certification": 4, "Google Data Analytics Certificate": 3,
            "Microsoft Azure Fundamentals": 2, "NPTEL Certification": 3},
    "ECE": {"Cisco CCNA": 4, "NPTEL Certification": 5, "AWS Cloud Practitioner": 1},
    "EE": {"NPTEL Certification": 6, "Google Data Analytics Certificate": 1},
    "ME": {"Autodesk Certified User": 5, "NPTEL Certification": 5},
}
# Skills that each company category tends to ask for
CATEGORY_REQUIREMENTS = {
    "Product-Based": ["Data Structures & Algorithms", "Python", "Java", "C++", "SQL", "Cloud Computing",
                      "Machine Learning", "JavaScript", "React", "Linux", "AWS Cloud Practitioner"],
    "Service-Based": ["Java", "SQL", "Python", "JavaScript", "Cloud Computing", "Linux",
                      "Oracle Java SE Certification", "Microsoft Azure Fundamentals"],
    "Consulting": ["SQL", "Data Analytics", "Python", "Machine Learning",
                   "Google Data Analytics Certificate"],
    "Core Engineering": ["MATLAB", "Embedded Systems", "Power Systems", "AutoCAD", "VLSI Design",
                         "C++", "Cisco CCNA", "Autodesk Certified User", "NPTEL Certification"],
}
# Skills that (in this synthetic data) slightly improve placement odds
HELPFUL_SKILLS = {"Data Structures & Algorithms": 0.06, "Cloud Computing": 0.03,
                  "Machine Learning": 0.03, "Embedded Systems": 0.03, "SQL": 0.02}

YEAR_SALARY_FACTOR = {2023: 0.92, 2024: 1.0, 2025: 1.06}
# Placement season runs Aug (previous year) .. May. Weight = share of offers per month.
SEASON_MONTHS = [(8, 0.13), (9, 0.19), (10, 0.16), (11, 0.12), (12, 0.08),
                 (1, 0.10), (2, 0.09), (3, 0.06), (4, 0.04), (5, 0.03)]
ONGOING_LAST_MONTH = 3        # ongoing batch: offers recorded only up to March

FIRST_NAMES = [
    "Aarav", "Aditi", "Aditya", "Akash", "Ananya", "Anjali", "Arjun", "Ayesha", "Bhavya", "Chetan",
    "Deepak", "Diya", "Gaurav", "Gurpreet", "Harsh", "Ishaan", "Ishita", "Jasleen", "Karan", "Kavya",
    "Kriti", "Manish", "Meera", "Mohit", "Naina", "Neha", "Nikhil", "Pooja", "Pranav", "Priya",
    "Rahul", "Riya", "Rohan", "Sakshi", "Sameer", "Sanya", "Shivam", "Shreya", "Simran", "Sneha",
    "Tanvi", "Tarun", "Uday", "Varun", "Vikram", "Yash", "Zoya", "Harleen", "Kunal", "Lavanya",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Kaur", "Mehta", "Malhotra", "Chopra", "Bansal", "Agarwal",
    "Reddy", "Nair", "Iyer", "Patel", "Joshi", "Kapoor", "Saini", "Thakur", "Rana", "Sethi",
    "Arora", "Bhatia", "Khanna", "Mishra", "Pandey", "Yadav", "Chauhan", "Dhillon", "Grewal", "Sood",
]


def weighted_choice(rng, weights):
    """Pick one key from a {item: weight} dict."""
    items = [k for k, w in weights.items() if w > 0]
    return rng.choices(items, weights=[weights[k] for k in items], k=1)[0]


def weighted_sample(rng, weights, k):
    """Pick k DIFFERENT keys from a {item: weight} dict."""
    pool = dict(weights)
    chosen = []
    for _ in range(min(k, len(pool))):
        item = weighted_choice(rng, pool)
        chosen.append(item)
        pool.pop(item)
    return chosen


def random_offer_date(rng, batch):
    months = SEASON_MONTHS
    if batch == ONGOING_BATCH:
        months = [m for m in SEASON_MONTHS if m[0] >= 8 or m[0] <= ONGOING_LAST_MONTH]
    month = rng.choices([m for m, _ in months], weights=[w for _, w in months], k=1)[0]
    year = batch - 1 if month >= 8 else batch
    return date(year, month, rng.randint(1, 28))


def generate(rng):
    """Build all rows in memory. Returns a dict of lists."""
    skill_names = TECH_SKILLS + CERTIFICATIONS
    skill_ids = {name: i + 1 for i, name in enumerate(skill_names)}
    company_ids = {c[0]: i + 1 for i, c in enumerate(COMPANIES)}

    students, eligibility, student_skills, placements = [], [], [], []
    hires_by_company_batch = set()

    for batch in BATCHES:
        for dept, _, size in DEPARTMENTS:
            for n in range(1, size + 1):
                sid = f"{batch % 100}{dept}{n:03d}"
                first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
                cgpa = round(min(9.8, max(5.2, rng.gauss(7.6, 0.9))), 2)
                email = f"{first.lower()}.{last.lower()}.{sid.lower()}@example.edu"
                students.append((sid, f"{first} {last}", dept, batch, cgpa, email, 1))

                eligible = 1 if (cgpa >= 6.0 and rng.random() > 0.04) else 0
                eligibility.append((sid, eligible, batch))

                # Skills and certifications
                pool = DEPT_SKILL_WEIGHTS[dept]
                skills = weighted_sample(rng, pool, rng.randint(2, min(6, len(pool) - 2)))
                n_certs = rng.choices([0, 1, 2], weights=[0.45, 0.4, 0.15], k=1)[0]
                skills += weighted_sample(rng, DEPT_CERT_WEIGHTS[dept], n_certs)
                student_skills.extend((sid, skill_ids[s]) for s in skills)

                if not eligible:
                    continue

                # Probability of being placed
                p = DEPT_BASE_PLACEMENT_RATE[dept] + (cgpa - 7.5) * 0.08 + 0.025 * n_certs
                p += sum(HELPFUL_SKILLS.get(s, 0) for s in skills)
                if batch == 2023:
                    p *= 0.95
                if batch == ONGOING_BATCH:
                    p *= 0.62          # season not finished yet
                p = min(0.97, max(0.10, p))

                if rng.random() < p:
                    status = "Placed"
                elif batch == ONGOING_BATCH and rng.random() < 0.10:
                    status = "Offer Pending"
                else:
                    continue

                weights = {c[0]: c[4] * DEPT_AFFINITY[dept][c[2]] for c in COMPANIES}
                company = COMPANIES[company_ids[weighted_choice(rng, weights)] - 1]
                name, _, category, base_ctc, _ = company

                package = base_ctc * YEAR_SALARY_FACTOR[batch]
                package *= rng.lognormvariate(0, 0.18) * (1 + (cgpa - 7.5) * 0.04)
                if category == "Product-Based" and rng.random() < 0.07:
                    package *= 1.8      # occasional premium offer
                package = round(min(60.0, max(3.0, package)), 2)

                placements.append((sid, company_ids[name], package, random_offer_date(rng, batch), status))
                hires_by_company_batch.add((name, batch))

    # Skills each company asked for in the batches it recruited from
    requirements = []
    for name, batch in sorted(hires_by_company_batch):
        category = next(c[2] for c in COMPANIES if c[0] == name)
        for skill in rng.sample(CATEGORY_REQUIREMENTS[category], rng.randint(3, 5)):
            requirements.append((company_ids[name], skill_ids[skill], batch))

    return {
        "skills": [(skill_ids[s], s, "Technical" if s in TECH_SKILLS else "Certification")
                   for s in skill_names],
        "companies": [(company_ids[c[0]], c[0], c[1], c[2], 1) for c in COMPANIES],
        "students": students,
        "eligibility": eligibility,
        "student_skills": student_skills,
        "placements": placements,
        "requirements": requirements,
    }


def seed():
    rng = random.Random(RANDOM_SEED)
    data = generate(rng)

    admin_pw = os.getenv("SEED_ADMIN_PASSWORD") or "admin123"
    viewer_pw = os.getenv("SEED_VIEWER_PASSWORD") or "viewer123"

    with transaction() as cur:
        # 1. Clear old data (children first)
        for table in ["users", "department_eligibility", "company_requirements", "student_skills",
                      "placements", "skills", "companies", "students", "departments"]:
            cur.execute(f"DELETE FROM {table}")  # table names are fixed constants, not user input
        cur.execute("ALTER TABLE companies AUTO_INCREMENT = 1")
        cur.execute("ALTER TABLE skills AUTO_INCREMENT = 1")

        # 2. Insert fresh sample data
        cur.executemany("INSERT INTO departments (dept_code, dept_name) VALUES (%s, %s)",
                        [(d[0], d[1]) for d in DEPARTMENTS])
        cur.executemany("INSERT INTO skills (skill_id, skill_name, skill_type) VALUES (%s, %s, %s)",
                        data["skills"])
        cur.executemany("INSERT INTO companies (company_id, company_name, industry, company_category, is_sample) "
                        "VALUES (%s, %s, %s, %s, %s)", data["companies"])
        cur.executemany("INSERT INTO students (student_id, student_name, department, batch_year, cgpa, email, is_sample) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)", data["students"])
        cur.executemany("INSERT INTO department_eligibility (student_id, eligible_for_placement, batch_year) "
                        "VALUES (%s, %s, %s)", data["eligibility"])
        cur.executemany("INSERT INTO student_skills (student_id, skill_id) VALUES (%s, %s)",
                        data["student_skills"])
        cur.executemany("INSERT INTO placements (student_id, company_id, package_lpa, placement_date, placement_status) "
                        "VALUES (%s, %s, %s, %s, %s)", data["placements"])
        cur.executemany("INSERT INTO company_requirements (company_id, skill_id, batch_year) VALUES (%s, %s, %s)",
                        data["requirements"])
        cur.executemany("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", [
            ("admin", generate_password_hash(admin_pw), "admin"),
            ("viewer", generate_password_hash(viewer_pw), "viewer"),
        ])

    summary = fetch_one(
        "SELECT COUNT(*) AS students, SUM(is_placed) AS placed, "
        "COUNT(DISTINCT batch_year) AS batches, COUNT(DISTINCT department) AS departments "
        "FROM vw_student_placements")
    print("Sample data created (FICTIONAL - for demonstration only)")
    print(f"  Departments : {summary['departments']}")
    print(f"  Batches     : {', '.join(map(str, BATCHES))} (ongoing: {ONGOING_BATCH})")
    print(f"  Students    : {summary['students']}")
    print(f"  Placed      : {int(summary['placed'])}")
    print(f"  Companies   : {len(data['companies'])}")
    print(f"  Skills      : {len(data['skills'])} ({len(CERTIFICATIONS)} certifications)")
    print(f"  Requirements: {len(data['requirements'])}")
    print("Login accounts:  admin / " + ("(SEED_ADMIN_PASSWORD)" if os.getenv("SEED_ADMIN_PASSWORD") else "admin123")
          + "   viewer / " + ("(SEED_VIEWER_PASSWORD)" if os.getenv("SEED_VIEWER_PASSWORD") else "viewer123"))


if __name__ == "__main__":
    try:
        seed()
    except DatabaseError as exc:
        print("ERROR:", exc)
        print("Did you run schema.sql first and fill in .env?")
