"""Insert one sample resume and one sample job description for testing.

Run from the repository root:

    backend\\.venv\\Scripts\\python.exe scripts\\seed.py

Options:
    --reset   Delete existing sample rows first, so repeated runs stay clean.

The sample pair is deliberately realistic — a fresh BCA graduate against a
junior Python/FastAPI role — so Phase 1's keyword-gap analysis has genuine
overlaps (Python, SQL, REST) and genuine gaps (Docker, CI/CD, testing) to find.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the backend package importable no matter which directory this is run from.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_session_factory, init_db  # noqa: E402
from app.models import JobDescription, ResumeVersion  # noqa: E402

SAMPLE_RESUME_TITLE = "Sample Resume — Fresh BCA Graduate"
SAMPLE_JD_TITLE = "Junior Python Developer"

SAMPLE_RESUME_TEXT = """\
AARAV SHARMA
Ahmedabad, Gujarat | aarav.sharma@example.com | +91 98XXXXXX21
github.com/aaravsharma-example | linkedin.com/in/aaravsharma-example

EDUCATION
Bachelor of Computer Applications (BCA), Gujarat University
2023 - 2026 | CGPA: 8.4 / 10
Relevant coursework: Data Structures, DBMS, Operating Systems, Web Technologies,
Software Engineering

TECHNICAL SKILLS
Languages: Python, JavaScript, Java (basic), SQL
Web: HTML5, CSS3, React, Flask, REST APIs
Databases: MySQL, SQLite
Tools: Git, GitHub, VS Code, Postman

PROJECTS
Library Management System (Jan 2026 - Apr 2026)
- Built a Flask web application to track book issues and returns for a
  college library of about 4,000 titles.
- Designed a normalised MySQL schema with 7 tables; wrote the queries powering
  the overdue-books report.
- Added a search feature that cut the time to locate a title from minutes to
  under 5 seconds.

Weather Dashboard (Aug 2025 - Sep 2025)
- Developed a React single-page app consuming a public weather REST API.
- Implemented client-side caching that reduced repeat API calls by roughly 60%.

Student Attendance Tracker (Feb 2025 - Mar 2025)
- Created a Python + SQLite desktop tool used by two faculty members to record
  attendance for 120 students.

EXPERIENCE
Web Development Intern, Nexus Softwares, Ahmedabad (May 2025 - Jul 2025)
- Fixed 20+ front-end bugs in a client dashboard built with React.
- Wrote SQL queries for a monthly reporting module used by the operations team.
- Participated in daily stand-ups and used Git for version control.

ACHIEVEMENTS
- Runner-up, Intra-college Hackathon 2025 (team of 3).
- Completed "Python for Everybody" specialisation (Coursera, 2024).

LANGUAGES
English (professional), Hindi (native), Gujarati (native)
"""

SAMPLE_JD_TEXT = """\
Junior Python Developer
TechNova Solutions Pvt. Ltd. - Ahmedabad (Hybrid)
Experience: 0 - 2 years | Full-time

ABOUT THE ROLE
We are looking for a Junior Python Developer to join our backend team. You will
help build and maintain REST APIs that power our customer-facing web platform,
working closely with senior engineers who will review your code and mentor you.

RESPONSIBILITIES
- Develop and maintain RESTful APIs using Python and FastAPI.
- Write clean, tested code and take part in peer code reviews.
- Work with PostgreSQL: write queries, design simple schemas, tune slow queries.
- Containerise services with Docker and support deployments through our CI/CD
  pipeline (GitHub Actions).
- Debug production issues and write clear post-mortems.
- Collaborate with the frontend team on API contracts.

REQUIRED SKILLS
- Strong fundamentals in Python 3 (data structures, OOP, error handling).
- Understanding of REST API design principles and HTTP.
- Working knowledge of SQL and relational database concepts.
- Familiarity with Git and collaborative development workflows.
- Ability to write unit tests (pytest preferred).
- Good written communication in English.

NICE TO HAVE
- Experience with FastAPI or Flask in a project setting.
- Exposure to Docker and containerised development.
- Familiarity with CI/CD concepts and GitHub Actions.
- Any experience with cloud platforms (AWS/Azure).
- Contributions to open-source projects.

WHAT WE OFFER
- Structured mentorship from senior backend engineers.
- Hybrid working (3 days in office).
- Annual learning budget for courses and certifications.
"""


def seed(reset: bool = False) -> None:
    """Create the schema if needed, then insert the sample resume and JD."""
    init_db()
    session_factory = get_session_factory()

    with session_factory() as session:
        if reset:
            removed_resumes = (
                session.query(ResumeVersion)
                .filter(ResumeVersion.title == SAMPLE_RESUME_TITLE)
                .delete()
            )
            removed_jds = (
                session.query(JobDescription)
                .filter(JobDescription.title == SAMPLE_JD_TITLE)
                .delete()
            )
            session.commit()
            print(f"Removed {removed_resumes} sample resume(s), {removed_jds} sample JD(s).")

        existing = (
            session.query(ResumeVersion)
            .filter(ResumeVersion.title == SAMPLE_RESUME_TITLE)
            .first()
        )
        if existing:
            print("Sample data already present. Re-run with --reset to replace it.")
            return

        resume = ResumeVersion(title=SAMPLE_RESUME_TITLE, raw_text=SAMPLE_RESUME_TEXT)
        jd = JobDescription(
            title=SAMPLE_JD_TITLE,
            company="TechNova Solutions Pvt. Ltd.",
            raw_text=SAMPLE_JD_TEXT,
        )
        session.add_all([resume, jd])
        session.commit()

        print("Seeded successfully:")
        print(f"  ResumeVersion  id={resume.id}  {resume.title}")
        print(f"  JobDescription id={jd.id}  {jd.title} @ {jd.company}")
        print()
        print("Overlaps to expect from gap analysis: Python, SQL, REST, Git, React")
        print("Gaps to expect: FastAPI, Docker, CI/CD, pytest, PostgreSQL")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="delete existing sample rows before inserting"
    )
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
