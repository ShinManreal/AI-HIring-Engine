import sqlite3
from datetime import datetime
import csv
import shutil
import os


DB_NAME = "hiring_engine.db"


def connect_db():
    return sqlite3.connect(DB_NAME)


def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            role TEXT,
            location TEXT,
            pay TEXT,
            schedule TEXT,
            must_haves TEXT,
            nice_to_haves TEXT,
            disqualifiers TEXT,
            evaluation_rules TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT,
            location TEXT,
            applied_role TEXT,
            resume_text TEXT,
            screening_answers TEXT,
            portfolio_links TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screening_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            client_id INTEGER,
            result TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            client_id INTEGER,
            script TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            client_id INTEGER,
            transcript TEXT,
            evaluation TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_client(client_name, role, location, pay, schedule, must_haves, nice_to_haves, disqualifiers, evaluation_rules):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO clients (
            client_name, role, location, pay, schedule, must_haves,
            nice_to_haves, disqualifiers, evaluation_rules, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_name,
        role,
        location,
        pay,
        schedule,
        must_haves,
        nice_to_haves,
        disqualifiers,
        evaluation_rules,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def get_clients():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM clients ORDER BY client_name")
    clients = cursor.fetchall()

    conn.close()
    return clients


def get_client(client_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    client = cursor.fetchone()

    conn.close()
    return client


def update_client(client_id, client_name, role, location, pay, schedule, must_haves, nice_to_haves, disqualifiers, evaluation_rules):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE clients
        SET client_name = ?,
            role = ?,
            location = ?,
            pay = ?,
            schedule = ?,
            must_haves = ?,
            nice_to_haves = ?,
            disqualifiers = ?,
            evaluation_rules = ?
        WHERE id = ?
    """, (
        client_name,
        role,
        location,
        pay,
        schedule,
        must_haves,
        nice_to_haves,
        disqualifiers,
        evaluation_rules,
        client_id
    ))

    conn.commit()
    conn.close()


def delete_client(client_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    cursor.execute("DELETE FROM screening_results WHERE client_id = ?", (client_id,))
    cursor.execute("DELETE FROM interview_scripts WHERE client_id = ?", (client_id,))
    cursor.execute("DELETE FROM evaluations WHERE client_id = ?", (client_id,))

    conn.commit()
    conn.close()


def add_candidate(candidate_name, location, applied_role, resume_text, screening_answers, portfolio_links):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO candidates (
            candidate_name, location, applied_role, resume_text,
            screening_answers, portfolio_links, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        candidate_name,
        location,
        applied_role,
        resume_text,
        screening_answers,
        portfolio_links,
        datetime.now().isoformat()
    ))

    candidate_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return candidate_id


def get_candidates():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM candidates ORDER BY created_at DESC")
    candidates = cursor.fetchall()

    conn.close()
    return candidates


def get_candidate(candidate_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
    candidate = cursor.fetchone()

    conn.close()
    return candidate


def update_candidate(candidate_id, candidate_name, location, applied_role, resume_text, screening_answers, portfolio_links):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE candidates
        SET candidate_name = ?,
            location = ?,
            applied_role = ?,
            resume_text = ?,
            screening_answers = ?,
            portfolio_links = ?
        WHERE id = ?
    """, (
        candidate_name,
        location,
        applied_role,
        resume_text,
        screening_answers,
        portfolio_links,
        candidate_id
    ))

    conn.commit()
    conn.close()


def delete_candidate(candidate_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
    cursor.execute("DELETE FROM screening_results WHERE candidate_id = ?", (candidate_id,))
    cursor.execute("DELETE FROM interview_scripts WHERE candidate_id = ?", (candidate_id,))
    cursor.execute("DELETE FROM evaluations WHERE candidate_id = ?", (candidate_id,))

    conn.commit()
    conn.close()


def save_screening_result(candidate_id, client_id, result):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO screening_results (
            candidate_id, client_id, result, created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        candidate_id,
        client_id,
        result,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def save_interview_script(candidate_id, client_id, script):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO interview_scripts (
            candidate_id, client_id, script, created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        candidate_id,
        client_id,
        script,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def save_evaluation(candidate_id, client_id, transcript, evaluation):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO evaluations (
            candidate_id, client_id, transcript, evaluation, created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        candidate_id,
        client_id,
        transcript,
        evaluation,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def count_records():
    conn = connect_db()
    cursor = conn.cursor()

    tables = [
        "clients",
        "candidates",
        "screening_results",
        "interview_scripts",
        "evaluations"
    ]

    counts = {}

    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cursor.fetchone()[0]

    conn.close()
    return counts


def run_safe_admin_command(command):
    conn = connect_db()
    cursor = conn.cursor()

    original_command = command.strip()
    command = original_command.lower()

    if command == "show counts":
        conn.close()
        return count_records()

    if command == "list clients":
        cursor.execute("SELECT id, client_name, role, location FROM clients ORDER BY id DESC")
        results = cursor.fetchall()
        conn.close()
        return results

    if command == "list candidates":
        cursor.execute("SELECT id, candidate_name, applied_role, location FROM candidates ORDER BY id DESC")
        results = cursor.fetchall()
        conn.close()
        return results

    if command == "show tables":
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        results = cursor.fetchall()
        conn.close()
        return results

    if command == "vacuum database":
        cursor.execute("VACUUM")
        conn.commit()
        conn.close()
        return "Database optimized."

    if command == "backup database":
        os.makedirs("backups", exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backups/hiring_engine_backup_{timestamp}.db"

        conn.close()
        shutil.copy(DB_NAME, backup_path)

        return f"Database backup created: {backup_path}"

    if command == "export clients csv":
        os.makedirs("exports", exist_ok=True)

        export_path = "exports/clients_export.csv"

        cursor.execute("SELECT * FROM clients")
        rows = cursor.fetchall()

        column_names = [description[0] for description in cursor.description]

        with open(export_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(column_names)
            writer.writerows(rows)

        conn.close()
        return f"Clients exported to: {export_path}"

    if command == "export candidates csv":
        os.makedirs("exports", exist_ok=True)

        export_path = "exports/candidates_export.csv"

        cursor.execute("SELECT * FROM candidates")
        rows = cursor.fetchall()

        column_names = [description[0] for description in cursor.description]

        with open(export_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(column_names)
            writer.writerows(rows)

        conn.close()
        return f"Candidates exported to: {export_path}"

    if command.startswith("delete client "):
        try:
            client_id = int(command.replace("delete client ", "").strip())
            conn.close()
            delete_client(client_id)
            return f"Client ID {client_id} deleted."
        except ValueError:
            conn.close()
            return "Invalid command. Use: delete client 1"

    if command.startswith("delete candidate "):
        try:
            candidate_id = int(command.replace("delete candidate ", "").strip())
            conn.close()
            delete_candidate(candidate_id)
            return f"Candidate ID {candidate_id} deleted."
        except ValueError:
            conn.close()
            return "Invalid command. Use: delete candidate 1"

    if command.startswith("find client "):
        search_term = original_command.replace("find client ", "").strip()

        cursor.execute("""
            SELECT id, client_name, role, location
            FROM clients
            WHERE client_name LIKE ?
               OR role LIKE ?
               OR location LIKE ?
               OR pay LIKE ?
               OR schedule LIKE ?
               OR must_haves LIKE ?
               OR nice_to_haves LIKE ?
               OR disqualifiers LIKE ?
               OR evaluation_rules LIKE ?
            ORDER BY id DESC
        """, tuple([f"%{search_term}%"] * 9))

        results = cursor.fetchall()
        conn.close()

        return results

    if command.startswith("find candidate "):
        search_term = original_command.replace("find candidate ", "").strip()

        cursor.execute("""
            SELECT id, candidate_name, applied_role, location
            FROM candidates
            WHERE candidate_name LIKE ?
               OR location LIKE ?
               OR applied_role LIKE ?
               OR resume_text LIKE ?
               OR screening_answers LIKE ?
               OR portfolio_links LIKE ?
            ORDER BY id DESC
        """, tuple([f"%{search_term}%"] * 6))

        results = cursor.fetchall()
        conn.close()

        return results

    conn.close()

    return """
Command not allowed.

Available commands:
show counts
list clients
list candidates
show tables
vacuum database
backup database
export clients csv
export candidates csv
delete client 1
delete candidate 1
find client huntsville
find candidate john
"""