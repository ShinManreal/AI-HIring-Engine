import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client


load_dotenv()


def get_secret(name):
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name)


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("Missing SUPABASE_URL.")

if not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_KEY.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def extract_field_from_ai_text(text, field_name):
    if not text:
        return ""

    lines = text.splitlines()
    field_name_lower = field_name.lower().strip()

    for line in lines:
        clean_line = line.strip()

        if clean_line.lower().startswith(field_name_lower + ":"):
            return clean_line.split(":", 1)[1].strip()

    return ""


def client_duplicate_exists(client_name, location):
    response = (
        supabase
        .table("clients")
        .select("id, client_name, location")
        .execute()
    )

    rows = response.data or []

    new_name = normalize_text(client_name)
    new_location = normalize_text(location)

    for row in rows:
        existing_name = normalize_text(row.get("client_name"))
        existing_location = normalize_text(row.get("location"))

        if existing_name == new_name and existing_location == new_location:
            return True

    return False


def candidate_duplicate_exists(candidate_name, location, applied_role):
    response = (
        supabase
        .table("candidates")
        .select("id, candidate_name, location, applied_role")
        .execute()
    )

    rows = response.data or []

    new_name = normalize_text(candidate_name)
    new_location = normalize_text(location)
    new_role = normalize_text(applied_role)

    for row in rows:
        existing_name = normalize_text(row.get("candidate_name"))
        existing_location = normalize_text(row.get("location"))
        existing_role = normalize_text(row.get("applied_role"))

        if existing_name == new_name and existing_location == new_location and existing_role == new_role:
            return True

    return False


# -----------------------------
# CLIENT FUNCTIONS
# -----------------------------

def add_client(
    client_name,
    role,
    location,
    pay,
    schedule,
    must_haves,
    nice_to_haves,
    disqualifiers,
    evaluation_rules
):
    formatted_client_needs = evaluation_rules or pay or ""

    data = {
        "client_name": client_name,
        "role": role or "Not specified",
        "location": location or "Not specified",
        "client_needs": formatted_client_needs,
        "formatted_client_needs": formatted_client_needs
    }

    response = supabase.table("clients").insert(data).execute()

    if response.data:
        return response.data[0].get("id")

    return None


def add_client_if_not_duplicate(
    client_name,
    role,
    location,
    pay,
    schedule,
    must_haves,
    nice_to_haves,
    disqualifiers,
    evaluation_rules
):
    if client_duplicate_exists(client_name, location):
        return {
            "status": "duplicate",
            "id": None,
            "message": "Duplicate client name and location."
        }

    client_id = add_client(
        client_name,
        role,
        location,
        pay,
        schedule,
        must_haves,
        nice_to_haves,
        disqualifiers,
        evaluation_rules
    )

    return {
        "status": "created",
        "id": client_id,
        "message": "Client created successfully."
    }


def get_clients():
    response = (
        supabase
        .table("clients")
        .select("*")
        .order("client_name")
        .execute()
    )

    rows = response.data or []

    return [
        (
            row.get("id"),
            row.get("client_name"),
            row.get("role"),
            row.get("location"),
            row.get("client_needs"),
            row.get("formatted_client_needs"),
            row.get("formatted_client_needs"),
            row.get("formatted_client_needs"),
            row.get("formatted_client_needs"),
            row.get("formatted_client_needs"),
            row.get("created_at"),
        )
        for row in rows
    ]


def get_client(client_id):
    response = (
        supabase
        .table("clients")
        .select("*")
        .eq("id", client_id)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return None

    row = rows[0]

    return (
        row.get("id"),
        row.get("client_name"),
        row.get("role"),
        row.get("location"),
        row.get("client_needs"),
        row.get("formatted_client_needs"),
        row.get("formatted_client_needs"),
        row.get("formatted_client_needs"),
        row.get("formatted_client_needs"),
        row.get("formatted_client_needs"),
        row.get("created_at"),
    )


def update_client(
    client_id,
    client_name,
    role,
    location,
    pay,
    schedule,
    must_haves,
    nice_to_haves,
    disqualifiers,
    evaluation_rules
):
    formatted_client_needs = evaluation_rules or pay or ""

    data = {
        "client_name": client_name,
        "role": role or "Not specified",
        "location": location or "Not specified",
        "client_needs": formatted_client_needs,
        "formatted_client_needs": formatted_client_needs
    }

    response = (
        supabase
        .table("clients")
        .update(data)
        .eq("id", client_id)
        .execute()
    )

    return response


def delete_client(client_id):
    response = (
        supabase
        .table("clients")
        .delete()
        .eq("id", client_id)
        .execute()
    )

    return response


# -----------------------------
# CANDIDATE FUNCTIONS
# -----------------------------

def add_candidate(
    candidate_name,
    location,
    applied_role,
    resume_text,
    screening_answers,
    portfolio_links
):
    data = {
        "candidate_name": candidate_name,
        "location": location,
        "applied_role": applied_role,
        "resume_text": resume_text,
        "screening_answers": screening_answers,
        "portfolio_links": portfolio_links,
        "candidate_status": "New"
    }

    response = supabase.table("candidates").insert(data).execute()

    if response.data:
        return response.data[0].get("id")

    return None


def add_candidate_if_not_duplicate(
    candidate_name,
    location,
    applied_role,
    resume_text,
    screening_answers,
    portfolio_links
):
    if candidate_duplicate_exists(candidate_name, location, applied_role):
        return {
            "status": "duplicate",
            "id": None,
            "message": "Duplicate candidate name, location, and applied role."
        }

    candidate_id = add_candidate(
        candidate_name,
        location,
        applied_role,
        resume_text,
        screening_answers,
        portfolio_links
    )

    return {
        "status": "created",
        "id": candidate_id,
        "message": "Candidate created successfully."
    }


def get_candidates():
    response = (
        supabase
        .table("candidates")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    rows = response.data or []

    return [
        (
            row.get("id"),
            row.get("candidate_name"),
            row.get("location"),
            row.get("applied_role"),
            row.get("resume_text"),
            row.get("screening_answers"),
            row.get("portfolio_links"),
            row.get("created_at"),
        )
        for row in rows
    ]


def get_candidate(candidate_id):
    response = (
        supabase
        .table("candidates")
        .select("*")
        .eq("id", candidate_id)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return None

    row = rows[0]

    return (
        row.get("id"),
        row.get("candidate_name"),
        row.get("location"),
        row.get("applied_role"),
        row.get("resume_text"),
        row.get("screening_answers"),
        row.get("portfolio_links"),
        row.get("created_at"),
    )


def update_candidate(
    candidate_id,
    candidate_name,
    location,
    applied_role,
    resume_text,
    screening_answers,
    portfolio_links
):
    data = {
        "candidate_name": candidate_name,
        "location": location,
        "applied_role": applied_role,
        "resume_text": resume_text,
        "screening_answers": screening_answers,
        "portfolio_links": portfolio_links,
    }

    response = (
        supabase
        .table("candidates")
        .update(data)
        .eq("id", candidate_id)
        .execute()
    )

    return response


def delete_candidate(candidate_id):
    response = (
        supabase
        .table("candidates")
        .delete()
        .eq("id", candidate_id)
        .execute()
    )

    return response


# -----------------------------
# AI OUTPUT SAVE FUNCTIONS
# -----------------------------

def save_screening_result(candidate_id, client_id, result):
    star_rating = extract_field_from_ai_text(result, "Star Rating")
    decision = extract_field_from_ai_text(result, "Decision")

    data = {
        "candidate_id": candidate_id,
        "client_id": client_id,
        "result": result,
        "star_rating": star_rating,
        "decision": decision
    }

    response = supabase.table("screening_results").insert(data).execute()

    if response.data:
        return response.data[0].get("id")

    return None


def save_interview_script(candidate_id, client_id, script):
    data = {
        "candidate_id": candidate_id,
        "client_id": client_id,
        "script": script
    }

    response = supabase.table("interview_scripts").insert(data).execute()

    if response.data:
        return response.data[0].get("id")

    return None


def save_evaluation(candidate_id, client_id, transcript, evaluation):
    star_rating = extract_field_from_ai_text(evaluation, "Star Rating")
    recommendation = extract_field_from_ai_text(evaluation, "Recommendation")

    data = {
        "candidate_id": candidate_id,
        "client_id": client_id,
        "transcript": transcript,
        "evaluation": evaluation,
        "star_rating": star_rating,
        "recommendation": recommendation
    }

    response = supabase.table("evaluations").insert(data).execute()

    if response.data:
        return response.data[0].get("id")

    return None


# -----------------------------
# DOCUMENT FUNCTIONS
# -----------------------------

def save_candidate_document(candidate_id, file_name, file_type, file_url, storage_path):
    data = {
        "candidate_id": candidate_id,
        "file_name": file_name,
        "file_type": file_type,
        "file_url": file_url,
        "storage_path": storage_path
    }

    response = supabase.table("candidate_documents").insert(data).execute()

    if response.data:
        return response.data[0].get("id")

    return None


def get_candidate_documents(candidate_id):
    response = (
        supabase
        .table("candidate_documents")
        .select("*")
        .eq("candidate_id", candidate_id)
        .order("created_at", desc=True)
        .execute()
    )

    return response.data or []


# -----------------------------
# STATUS HISTORY FUNCTIONS
# -----------------------------

def save_candidate_status_history(candidate_id, old_status, new_status, note):
    data = {
        "candidate_id": candidate_id,
        "old_status": old_status,
        "new_status": new_status,
        "note": note
    }

    response = supabase.table("candidate_status_history").insert(data).execute()

    if response.data:
        return response.data[0].get("id")

    return None


def update_candidate_status(candidate_id, new_status, note=""):
    candidate = get_candidate(candidate_id)

    old_status = ""

    response = (
        supabase
        .table("candidates")
        .select("candidate_status")
        .eq("id", candidate_id)
        .execute()
    )

    rows = response.data or []

    if rows:
        old_status = rows[0].get("candidate_status") or ""

    data = {
        "candidate_status": new_status
    }

    update_response = (
        supabase
        .table("candidates")
        .update(data)
        .eq("id", candidate_id)
        .execute()
    )

    save_candidate_status_history(candidate_id, old_status, new_status, note)

    return update_response


# -----------------------------
# ADMIN FUNCTIONS
# -----------------------------

def count_table(table_name):
    response = (
        supabase
        .table(table_name)
        .select("id", count="exact")
        .execute()
    )

    return response.count or 0


def count_records():
    tables = [
        "clients",
        "candidates",
        "screening_results",
        "interview_scripts",
        "evaluations"
    ]

    counts = {}

    for table in tables:
        try:
            counts[table] = count_table(table)
        except Exception:
            counts[table] = 0

    return counts


def list_clients_for_admin():
    response = (
        supabase
        .table("clients")
        .select("id, client_name, role, location, created_at")
        .order("id", desc=True)
        .execute()
    )

    return response.data or []


def list_candidates_for_admin():
    response = (
        supabase
        .table("candidates")
        .select("id, candidate_name, applied_role, location, candidate_status, created_at")
        .order("id", desc=True)
        .execute()
    )

    return response.data or []


def find_clients(search_term):
    response = (
        supabase
        .table("clients")
        .select("id, client_name, role, location, created_at")
        .ilike("client_name", f"%{search_term}%")
        .execute()
    )

    return response.data or []


def find_candidates(search_term):
    response = (
        supabase
        .table("candidates")
        .select("id, candidate_name, applied_role, location, candidate_status, created_at")
        .ilike("candidate_name", f"%{search_term}%")
        .execute()
    )

    return response.data or []


def run_safe_admin_command(command):
    original_command = command.strip()
    command = original_command.lower()

    if command == "show counts":
        return count_records()

    if command == "list clients":
        return list_clients_for_admin()

    if command == "list candidates":
        return list_candidates_for_admin()

    if command == "show tables":
        return [
            "clients",
            "candidates",
            "candidate_documents",
            "screening_results",
            "interview_scripts",
            "evaluations",
            "candidate_status_history"
        ]

    if command.startswith("find client "):
        search_term = original_command.replace("find client ", "").strip()
        return find_clients(search_term)

    if command.startswith("find candidate "):
        search_term = original_command.replace("find candidate ", "").strip()
        return find_candidates(search_term)

    if command.startswith("delete client "):
        try:
            client_id = int(command.replace("delete client ", "").strip())
            delete_client(client_id)
            return f"Client ID {client_id} deleted."
        except ValueError:
            return "Invalid command. Use: delete client 1"

    if command.startswith("delete candidate "):
        try:
            candidate_id = int(command.replace("delete candidate ", "").strip())
            delete_candidate(candidate_id)
            return f"Candidate ID {candidate_id} deleted."
        except ValueError:
            return "Invalid command. Use: delete candidate 1"

    return """
Command not allowed.

Available commands:
show counts
show tables
list clients
list candidates
delete client 1
delete candidate 1
find client huntsville
find candidate john
"""