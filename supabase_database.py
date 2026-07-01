import os
from dotenv import load_dotenv
from supabase import create_client

try:
    import streamlit as st
except Exception:
    st = None


load_dotenv()


def get_secret(name):
    if st is not None:
        try:
            if name in st.secrets:
                return st.secrets[name]
        except Exception:
            pass

    return os.getenv(name)


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("Missing SUPABASE_URL.")

if not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_KEY.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# -----------------------------
# GENERAL HELPERS
# -----------------------------

def clean_search_value(value):
    if value is None:
        return ""

    cleaned = str(value).strip()
    cleaned = cleaned.replace(",", " ")
    cleaned = cleaned.replace("%", "")
    cleaned = cleaned.replace("*", "")
    return cleaned


def candidate_row_to_tuple(row):
    return (
        row.get("id"),
        row.get("candidate_name") or "",
        row.get("location") or "",
        row.get("applied_role") or "",
        row.get("resume_text") or "",
        row.get("screening_answers") or "",
        row.get("portfolio_links") or "",
        row.get("created_at") or "",
        row.get("email") or "",
        row.get("phone") or "",
        row.get("candidate_status") or "Prospects",
        row.get("matched_client_id"),
        row.get("matched_client_name") or "",
        row.get("matched_client_distance_miles")
    )


def client_row_to_tuple(row):
    client_needs = row.get("client_needs") or ""
    formatted_client_needs = row.get("formatted_client_needs") or client_needs

    return (
        row.get("id"),
        row.get("client_name") or "",
        row.get("role") or "",
        row.get("location") or "",
        client_needs,
        client_needs,
        client_needs,
        client_needs,
        client_needs,
        formatted_client_needs
    )


def fetch_all_rows(table_name, order_column="id", desc=True, select_columns="*"):
    all_rows = []
    batch_size = 1000
    start = 0

    while True:
        response = (
            supabase
            .table(table_name)
            .select(select_columns)
            .order(order_column, desc=desc)
            .range(start, start + batch_size - 1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < batch_size:
            break

        start += batch_size

    return all_rows


# -----------------------------
# CLIENTS
# -----------------------------

def add_client(
    client_name,
    role,
    location,
    client_needs,
    pay="",
    schedule="",
    must_haves="",
    nice_to_haves="",
    formatted_client_needs=""
):
    data = {
        "client_name": client_name,
        "role": role,
        "location": location,
        "client_needs": client_needs,
        "formatted_client_needs": formatted_client_needs or client_needs
    }

    response = supabase.table("clients").insert(data).execute()
    rows = response.data or []

    if rows:
        return rows[0].get("id")

    return None


def get_clients():
    rows = fetch_all_rows("clients", order_column="id", desc=True)
    return [client_row_to_tuple(row) for row in rows]


def search_clients(search_term="", limit=50):
    cleaned_search = clean_search_value(search_term)

    query = (
        supabase
        .table("clients")
        .select("id, client_name, role, location, client_needs, formatted_client_needs")
        .order("client_name", desc=False)
        .limit(limit)
    )

    if cleaned_search:
        query = query.or_(
            f"client_name.ilike.%{cleaned_search}%,"
            f"role.ilike.%{cleaned_search}%,"
            f"location.ilike.%{cleaned_search}%,"
            f"client_needs.ilike.%{cleaned_search}%,"
            f"formatted_client_needs.ilike.%{cleaned_search}%"
        )

    response = query.execute()
    rows = response.data or []

    return [client_row_to_tuple(row) for row in rows]


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

    return client_row_to_tuple(rows[0])


def update_client(
    client_id,
    client_name,
    role,
    location,
    client_needs,
    pay="",
    schedule="",
    must_haves="",
    nice_to_haves="",
    formatted_client_needs=""
):
    data = {
        "client_name": client_name,
        "role": role,
        "location": location,
        "client_needs": client_needs,
        "formatted_client_needs": formatted_client_needs or client_needs
    }

    response = (
        supabase
        .table("clients")
        .update(data)
        .eq("id", client_id)
        .execute()
    )

    return response.data


def delete_client(client_id):
    response = (
        supabase
        .table("clients")
        .delete()
        .eq("id", client_id)
        .execute()
    )

    return response.data


def client_duplicate_exists(client_name, location):
    response = (
        supabase
        .table("clients")
        .select("id")
        .eq("client_name", client_name)
        .eq("location", location)
        .limit(1)
        .execute()
    )

    rows = response.data or []
    return len(rows) > 0


# -----------------------------
# CANDIDATES
# -----------------------------

def add_candidate(
    candidate_name,
    location,
    applied_role,
    resume_text,
    screening_answers,
    portfolio_links="",
    email="",
    phone="",
    candidate_status="Prospects",
    matched_client_id=None,
    matched_client_name="",
    matched_client_distance_miles=None
):
    data = {
        "candidate_name": candidate_name,
        "email": email,
        "phone": phone,
        "location": location,
        "applied_role": applied_role,
        "resume_text": resume_text,
        "screening_answers": screening_answers,
        "portfolio_links": portfolio_links or "",
        "candidate_status": candidate_status or "Prospects",
        "matched_client_id": matched_client_id,
        "matched_client_name": matched_client_name,
        "matched_client_distance_miles": matched_client_distance_miles
    }

    response = supabase.table("candidates").insert(data).execute()
    rows = response.data or []

    if rows:
        return rows[0].get("id")

    return None


def get_candidates():
    rows = fetch_all_rows("candidates", order_column="candidate_name", desc=False)
    return [candidate_row_to_tuple(row) for row in rows]


def search_candidates(
    search_term="",
    status_filter="",
    role_filter="",
    limit=50,
    offset=0
):
    cleaned_search = clean_search_value(search_term)

    select_columns = (
        "id, candidate_name, location, applied_role, resume_text, "
        "screening_answers, portfolio_links, created_at, email, phone, "
        "candidate_status, matched_client_id, matched_client_name, "
        "matched_client_distance_miles"
    )

    query = (
        supabase
        .table("candidates")
        .select(select_columns)
        .order("candidate_name", desc=False)
    )

    if status_filter:
        query = query.eq("candidate_status", status_filter)

    if role_filter:
        query = query.eq("applied_role", role_filter)

    if cleaned_search:
        query = query.or_(
            f"candidate_name.ilike.%{cleaned_search}%,"
            f"location.ilike.%{cleaned_search}%,"
            f"applied_role.ilike.%{cleaned_search}%,"
            f"candidate_status.ilike.%{cleaned_search}%,"
            f"matched_client_name.ilike.%{cleaned_search}%,"
            f"email.ilike.%{cleaned_search}%,"
            f"phone.ilike.%{cleaned_search}%"
        )

    query = query.range(offset, offset + limit - 1)

    response = query.execute()
    rows = response.data or []

    return [candidate_row_to_tuple(row) for row in rows]


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

    return candidate_row_to_tuple(rows[0])


def update_candidate(
    candidate_id,
    candidate_name,
    location,
    applied_role,
    resume_text,
    screening_answers,
    portfolio_links="",
    email="",
    phone="",
    candidate_status="Prospects",
    matched_client_id=None,
    matched_client_name="",
    matched_client_distance_miles=None
):
    data = {
        "candidate_name": candidate_name,
        "email": email,
        "phone": phone,
        "location": location,
        "applied_role": applied_role,
        "resume_text": resume_text,
        "screening_answers": screening_answers,
        "portfolio_links": portfolio_links or "",
        "candidate_status": candidate_status or "Prospects",
        "matched_client_id": matched_client_id,
        "matched_client_name": matched_client_name,
        "matched_client_distance_miles": matched_client_distance_miles
    }

    response = (
        supabase
        .table("candidates")
        .update(data)
        .eq("id", candidate_id)
        .execute()
    )

    return response.data


def delete_candidate(candidate_id):
    response = (
        supabase
        .table("candidates")
        .delete()
        .eq("id", candidate_id)
        .execute()
    )

    return response.data


def candidate_duplicate_exists(candidate_name, location, applied_role):
    response = (
        supabase
        .table("candidates")
        .select("id")
        .eq("candidate_name", candidate_name)
        .eq("location", location)
        .eq("applied_role", applied_role)
        .limit(1)
        .execute()
    )

    rows = response.data or []
    return len(rows) > 0


# -----------------------------
# CANDIDATE EXTRA FIELDS
# -----------------------------

def get_candidate_extra(candidate_id):
    default_extra = {
        "interview_date": "",
        "interviewer": "",
        "short_summary": "",
        "latest_screening_result": "",
        "latest_interview_script": "",
        "latest_evaluation": ""
    }

    try:
        response = (
            supabase
            .table("candidates")
            .select(
                "interview_date, interviewer, short_summary, "
                "latest_screening_result, latest_interview_script, latest_evaluation"
            )
            .eq("id", candidate_id)
            .execute()
        )

        rows = response.data or []

        if not rows:
            return default_extra

        row = rows[0]

        return {
            "interview_date": row.get("interview_date") or "",
            "interviewer": row.get("interviewer") or "",
            "short_summary": row.get("short_summary") or "",
            "latest_screening_result": row.get("latest_screening_result") or "",
            "latest_interview_script": row.get("latest_interview_script") or "",
            "latest_evaluation": row.get("latest_evaluation") or ""
        }

    except Exception:
        return default_extra


def update_candidate_extra(candidate_id, data):
    response = (
        supabase
        .table("candidates")
        .update(data)
        .eq("id", candidate_id)
        .execute()
    )

    return response.data


# -----------------------------
# AI OUTPUT TABLES
# -----------------------------

def save_screening_result(candidate_id, client_id, result, star_rating="", decision=""):
    data = {
        "candidate_id": candidate_id,
        "client_id": client_id,
        "result": result,
        "star_rating": star_rating,
        "decision": decision
    }

    response = supabase.table("screening_results").insert(data).execute()
    rows = response.data or []

    if rows:
        return rows[0].get("id")

    return None


def save_interview_script(candidate_id, client_id, script):
    data = {
        "candidate_id": candidate_id,
        "client_id": client_id,
        "script": script
    }

    response = supabase.table("interview_scripts").insert(data).execute()
    rows = response.data or []

    if rows:
        return rows[0].get("id")

    return None


def save_evaluation(candidate_id, client_id, transcript, evaluation, star_rating="", recommendation=""):
    data = {
        "candidate_id": candidate_id,
        "client_id": client_id,
        "transcript": transcript,
        "evaluation": evaluation,
        "star_rating": star_rating,
        "recommendation": recommendation
    }

    response = supabase.table("evaluations").insert(data).execute()
    rows = response.data or []

    if rows:
        return rows[0].get("id")

    return None


# -----------------------------
# COUNTS / ADMIN HELPERS
# -----------------------------

def count_table(table_name):
    try:
        response = (
            supabase
            .table(table_name)
            .select("id", count="exact")
            .limit(1)
            .execute()
        )

        return response.count or 0

    except Exception:
        return 0


def count_records():
    return {
        "clients": count_table("clients"),
        "candidates": count_table("candidates"),
        "screening_results": count_table("screening_results"),
        "interview_scripts": count_table("interview_scripts"),
        "evaluations": count_table("evaluations")
    }


def run_safe_admin_command(command):
    cleaned_command = str(command).strip()
    lowered = cleaned_command.lower()

    if lowered == "show counts":
        return count_records()

    if lowered == "show tables":
        return [
            "clients",
            "candidates",
            "screening_results",
            "interview_scripts",
            "evaluations",
            "candidate_documents",
            "candidate_status_history"
        ]

    if lowered == "list clients":
        return search_clients("", limit=50)

    if lowered == "list candidates":
        return search_candidates("", limit=50)

    if lowered.startswith("find client "):
        search = cleaned_command[12:].strip()
        return search_clients(search, limit=50)

    if lowered.startswith("find candidate "):
        search = cleaned_command[15:].strip()
        return search_candidates(search, limit=50)

    if lowered.startswith("delete client "):
        try:
            client_id = int(lowered.replace("delete client ", "").strip())
            delete_client(client_id)
            return f"Deleted client ID {client_id}."
        except Exception as error:
            return f"Could not delete client. Error: {error}"

    if lowered.startswith("delete candidate "):
        try:
            candidate_id = int(lowered.replace("delete candidate ", "").strip())
            delete_candidate(candidate_id)
            return f"Deleted candidate ID {candidate_id}."
        except Exception as error:
            return f"Could not delete candidate. Error: {error}"

    return "Command not recognized or not allowed."