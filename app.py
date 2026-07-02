import os
import re
import json
import hashlib
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

from supabase_database import (
    add_client,
    get_clients,
    get_client,
    search_clients,
    update_client,
    delete_client,
    client_duplicate_exists,
    add_candidate,
    get_candidate,
    search_candidates,
    update_candidate,
    delete_candidate,
    candidate_duplicate_exists,
    get_candidate_extra,
    update_candidate_extra,
    save_screening_result,
    save_interview_script,
    save_evaluation,
    count_records,
    run_safe_admin_command
)

from resume_parser import extract_resume_text
from ai_engine import generate_ai_response as ask_ai

from prompts import (
    client_formatter_prompt,
    screening_prompt,
    interview_script_prompt,
    evaluation_prompt
)


load_dotenv()


st.set_page_config(
    page_title="AI Hiring Engine",
    layout="wide"
)


# -----------------------------
# USERS AND SECURITY
# -----------------------------

APP_USERS = {
    "Leesa_Repp": {"name": "Leesa", "role": "admin"},
    "Shin_Repp": {"name": "Shin", "role": "admin"},
    "Claire_Repp": {"name": "Claire", "role": "recruiter"},
    "JR_Repp": {"name": "JR", "role": "recruiter"},
    "Nani_Repp": {"name": "Nani", "role": "recruiter"}
}


def get_secret(name):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass

    return os.getenv(name)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def homepage_login():
    st.markdown(
        """
        <div style="text-align:center; padding-top:40px;">
            <h1>AI Hiring Engine</h1>
            <p style="font-size:18px;">Secure REPP Talent Recruiting System</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        st.subheader("Login Required")

        username = st.text_input("Username", key="homepage_username")
        password = st.text_input("Password", type="password", key="homepage_password")

        if st.button("Login", use_container_width=True):
            password_hash = get_secret("APP_PASSWORD_HASH")

            if username in APP_USERS and hash_password(password) == password_hash:
                st.session_state.app_logged_in = True
                st.session_state.current_username = username
                st.session_state.current_user_name = APP_USERS[username]["name"]
                st.session_state.current_user_role = APP_USERS[username]["role"]
                st.success("Login successful.")
                st.rerun()
            else:
                st.error("Invalid username or password.")

        st.caption("Authorized REPP Talent users only.")


def require_app_login():
    if "app_logged_in" not in st.session_state:
        st.session_state.app_logged_in = False

    if not st.session_state.app_logged_in:
        homepage_login()
        st.stop()


def is_admin_user():
    return st.session_state.get("current_user_role") == "admin"


def require_admin():
    if not is_admin_user():
        st.error("You do not have administrator access.")
        st.stop()


def logout_button():
    with st.sidebar:
        st.divider()
        user_name = st.session_state.get("current_user_name", "User")
        user_role = st.session_state.get("current_user_role", "recruiter")

        st.caption(f"Logged in as: {user_name}")
        st.caption(f"Role: {user_role.title()}")

        if st.button("Logout"):
            st.session_state.app_logged_in = False
            st.session_state.current_username = ""
            st.session_state.current_user_name = ""
            st.session_state.current_user_role = ""
            st.session_state.selected_candidate_profile_id = None
            st.rerun()


# -----------------------------
# CONSTANTS
# -----------------------------

APPLIED_ROLE_OPTIONS = [
    "",
    "Photographer",
    "VA",
    "Editor",
    "Social Media Manager",
    "Real Estate Media"
]


CANDIDATE_STATUS_OPTIONS = [
    "Prospects",
    "Screen - PASS",
    "Initial Interview",
    "Pass: Ready for Leesa",
    "Leesa Interview",
    "Leesa Interview Complete",
    "Potential Finalists",
    "NO SHOWS",
    "Presented to Client",
    "Hired",
    "VA's Passed but Not Hired",
    "Passed but Not Hired",
    "BACKUP Candidates",
    "#NOPE"
]


READ_ONLY_STATUSES = [
    "#NOPE",
    "Leesa Interview Complete",
    "Potential Finalists",
    "Presented to Client",
    "Hired",
    "VA's Passed but Not Hired",
    "Passed but Not Hired",
    "BACKUP Candidates"
]


SCREENABLE_STATUSES = [
    "Prospects",
    "Screen - PASS"
]


INTERVIEW_ACTION_STATUSES = [
    "Initial Interview",
    "Pass: Ready for Leesa",
    "Leesa Interview"
]


INTERVIEWER_OPTIONS = [
    "",
    "Shin",
    "Claire",
    "JR",
    "Nani",
    "Leesa"
]


REMOTE_NEED_MATCH_ROLES = [
    "VA",
    "Editor",
    "Social Media Manager"
]


PHOTOGRAPHER_SCREENING_COLUMNS = [
    "P - If your best friend had to describe your personality and what matters most to you in life, what would they say?",
    "P - Why does this job interest you personally?",
    "P - Have you ever worked in a role where you were the face of the company - like a server, cashier, receptionist, etc.? If so, tell us a bit about it.",
    "P - Photo/Video/ Drone Experience",
    "P - What's your availability?",
    "P - Reliable Vehicle?"
]


VA_SCREENING_COLUMNS = [
    "VA - What are your available working hours in EST?",
    "VA - This role includes some client messaging and light social media support. How do you handle urgent or stressed clients professionally?",
    "VA - Have you used AI tools in your work? If so, how have you used them to improve speed or accuracy?",
    "VA - What tools have you used in real estate media workflows?",
    "VA - If you noticed editing issues or a missing room close to the delivery deadline, how would you handle it?",
    "VA - You log in and see a batch of photos that must be delivered by 9 a.m. EST. Walk us step-by-step through what you would check before sending them to the client.",
    "VA - Describe your experience working with real estate media or real estate companies. Have you performed Quality Control (QC) on listing photos?"
]


REAL_ESTATE_MEDIA_ADMIN_SCREENING_COLUMNS = [
    "A - What’s your typical weekly availability look like?",
    "A - Why does this job interest you personally?",
    "A - What experience do you have using CRMs, scheduling software, project management tools, AI tools, or other business systems?",
    "A - This role requires frequent communication with clients, photographers, and team members. How would you describe your communication style, and what do you enjoy most about working with people?",
    "A - Describe your experience working remotely. How do you stay organized, self-motivated, and communicate effectively while working independently?",
    "Long text",
    "communicate effectively while working independently?"
]


# -----------------------------
# BASIC HELPERS
# -----------------------------

def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def normalize_header(value):
    if value is None:
        return ""

    return (
        str(value)
        .replace("\ufeff", "")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
        .lower()
    )


def clean_dataframe_columns(df):
    df.columns = [
        str(column)
        .replace("\ufeff", "")
        .replace("\n", " ")
        .replace("\r", " ")
        .strip()
        for column in df.columns
    ]

    return df


def is_blank_value(value):
    if pd.isna(value):
        return True

    cleaned_value = str(value).strip()

    if cleaned_value == "":
        return True

    if cleaned_value.lower() in ["nan", "none", "null"]:
        return True

    return False


def row_is_fully_blank(row):
    for value in row.values:
        if not is_blank_value(value):
            return False

    return True


def row_looks_like_header(row):
    common_headers = [
        "stage",
        "full name",
        "candidate name",
        "name",
        "email",
        "phone",
        "location",
        "status",
        "client:",
        "company name"
    ]

    row_values = []

    for value in row.values:
        if not is_blank_value(value):
            row_values.append(normalize_header(value))

    if not row_values:
        return False

    match_count = 0

    for value in row_values:
        if value in common_headers:
            match_count += 1

    return match_count >= 2


def safe_value(row, column_name):
    target = normalize_header(column_name)

    for actual_column in row.index:
        if normalize_header(actual_column) == target:
            value = row[actual_column]

            if pd.isna(value):
                return ""

            return str(value).strip()

    return ""


def get_first_available_value(row, possible_columns):
    for column in possible_columns:
        value = safe_value(row, column)
        if value:
            return value

    return ""


def row_preview(row, max_items=8):
    preview = {}

    for index, column in enumerate(row.index):
        if index >= max_items:
            break

        value = row[column]

        if pd.isna(value):
            preview[str(column)] = ""
        else:
            preview[str(column)] = str(value)[:150]

    return preview


def build_failure(row_number, reason, row=None, extra=None):
    failure = {
        "row": row_number,
        "reason": reason
    }

    if extra:
        failure.update(extra)

    if row is not None:
        failure["available_headers"] = list(row.index)
        failure["row_preview"] = row_preview(row)

    return failure


def map_applied_role(raw_role):
    cleaned_role = normalize_text(raw_role)

    if not cleaned_role:
        return ""

    role_map = {
        "real estate photographer": "Photographer",
        "photographer": "Photographer",
        "photography": "Photographer",
        "photo": "Photographer",
        "virtual assistant": "VA",
        "va": "VA",
        "real estate media va": "VA",
        "real estate media admin & ops": "Real Estate Media",
        "real estate media admin and ops": "Real Estate Media",
        "real estate media admin": "Real Estate Media",
        "real estate media admin ops": "Real Estate Media",
        "admin & ops": "Real Estate Media",
        "admin and ops": "Real Estate Media",
        "admin": "Real Estate Media",
        "real estate media": "Real Estate Media",
        "editor": "Editor",
        "photo editor": "Editor",
        "video editor": "Editor",
        "social media manager": "Social Media Manager",
        "social media": "Social Media Manager",
        "smm": "Social Media Manager"
    }

    if cleaned_role in role_map:
        return role_map[cleaned_role]

    if "photographer" in cleaned_role or "photography" in cleaned_role:
        return "Photographer"

    if "virtual assistant" in cleaned_role or cleaned_role == "va":
        return "VA"

    if "admin" in cleaned_role or "ops" in cleaned_role:
        return "Real Estate Media"

    if "editor" in cleaned_role:
        return "Editor"

    if "social media" in cleaned_role:
        return "Social Media Manager"

    return ""


def normalize_candidate_status(raw_status):
    cleaned_status = normalize_text(raw_status)

    if not cleaned_status:
        return ""

    for status in CANDIDATE_STATUS_OPTIONS:
        if normalize_text(status) == cleaned_status:
            return status

    status_map = {
        "prospect": "Prospects",
        "prospects": "Prospects",
        "screen pass": "Screen - PASS",
        "screen - pass": "Screen - PASS",
        "initial interview": "Initial Interview",
        "ready for leesa": "Pass: Ready for Leesa",
        "pass ready for leesa": "Pass: Ready for Leesa",
        "leesa interview": "Leesa Interview",
        "leesa interview complete": "Leesa Interview Complete",
        "potential finalist": "Potential Finalists",
        "potential finalists": "Potential Finalists",
        "no show": "NO SHOWS",
        "no shows": "NO SHOWS",
        "presented to client": "Presented to Client",
        "hired": "Hired",
        "vas passed but not hired": "VA's Passed but Not Hired",
        "va's passed but not hired": "VA's Passed but Not Hired",
        "passed but not hired": "Passed but Not Hired",
        "backup": "BACKUP Candidates",
        "backup candidates": "BACKUP Candidates",
        "#nope": "#NOPE",
        "nope": "#NOPE"
    }

    return status_map.get(cleaned_status, "")


def is_read_only_candidate(candidate_status):
    return candidate_status in READ_ONLY_STATUSES


def can_screen_candidate(candidate_status):
    return candidate_status in SCREENABLE_STATUSES


def can_interview_candidate(candidate_status):
    return candidate_status in INTERVIEW_ACTION_STATUSES


# -----------------------------
# FREE GEOMAPPING
# -----------------------------

def geocode_location(location_text):
    if not location_text or normalize_text(location_text) == "not specified":
        return None

    if "geocode_cache" not in st.session_state:
        st.session_state.geocode_cache = {}

    cache_key = normalize_text(location_text)

    if cache_key in st.session_state.geocode_cache:
        return st.session_state.geocode_cache[cache_key]

    try:
        geolocator = Nominatim(
            user_agent="repp_ai_hiring_engine_free_geocoder"
        )

        result = geolocator.geocode(
            location_text,
            timeout=10
        )

        if not result:
            st.session_state.geocode_cache[cache_key] = None
            return None

        coordinates = (
            result.latitude,
            result.longitude
        )

        st.session_state.geocode_cache[cache_key] = coordinates
        return coordinates

    except Exception:
        st.session_state.geocode_cache[cache_key] = None
        return None


def find_nearest_client(candidate_location):
    candidate_coordinates = geocode_location(candidate_location)

    if not candidate_coordinates:
        return None, "", None

    clients = get_clients()

    nearest_client_id = None
    nearest_client_name = ""
    nearest_distance = None

    for client in clients:
        client_id = client[0]
        client_location = client[3] or ""
        client_display_name = get_client_display_name(client)

        client_coordinates = geocode_location(client_location)

        if not client_coordinates:
            continue

        distance = geodesic(candidate_coordinates, client_coordinates).miles

        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_client_id = client_id
            nearest_client_name = client_display_name

    if nearest_distance is None:
        return None, "", None

    return nearest_client_id, nearest_client_name, round(nearest_distance, 2)


# -----------------------------
# CLIENT DISPLAY + ROLE-BASED MATCHING
# -----------------------------

def extract_field_from_notes(notes, field_name):
    if not notes:
        return ""

    pattern = rf"{re.escape(field_name)}:\s*(.*)"
    match = re.search(pattern, str(notes), flags=re.IGNORECASE)

    if not match:
        return ""

    value = match.group(1).strip()

    if value.lower() in ["not specified", "none", "nan", ""]:
        return ""

    return value


def get_client_display_name(client):
    if not client:
        return ""

    saved_client_name = client[1] or ""
    client_needs = client[9] or client[4] or ""

    contact_name = extract_field_from_notes(client_needs, "Contact Name")
    client_name_from_notes = extract_field_from_notes(client_needs, "Client Name")
    company_name = extract_field_from_notes(client_needs, "Company Name")

    # Display priority:
    # 1. Contact Name = actual person/client name
    # 2. Client Name = saved client/contact name from notes
    # 3. Database client_name
    # 4. Company Name only as last fallback
    return contact_name or client_name_from_notes or saved_client_name or company_name


def role_uses_ai_need_matching(applied_role):
    return applied_role in REMOTE_NEED_MATCH_ROLES


def client_role_matches_candidate_role(client, applied_role):
    client_role = normalize_text(client[2])
    client_needs = normalize_text(client[9] or client[4])

    if applied_role == "VA":
        keywords = [
            "virtual assistant",
            "va",
            "admin assistant",
            "assistant",
            "operations",
            "admin",
            "real estate media va",
            "qc",
            "quality control",
            "delivery",
            "client messaging",
            "light social media",
            "crm"
        ]

    elif applied_role == "Editor":
        keywords = [
            "editor",
            "photo editor",
            "video editor",
            "editing",
            "lightroom",
            "photoshop",
            "qc",
            "quality control",
            "media editing",
            "delivery"
        ]

    elif applied_role == "Social Media Manager":
        keywords = [
            "social media manager",
            "social media",
            "content",
            "instagram",
            "facebook",
            "tiktok",
            "reels",
            "marketing",
            "content creation",
            "posts"
        ]

    else:
        return False

    combined_text = f"{client_role} {client_needs}"

    for keyword in keywords:
        if keyword in combined_text:
            return True

    return False


def get_relevant_clients_for_candidate_role(applied_role, max_clients=25):
    clients = get_clients()
    relevant_clients = []

    for client in clients:
        if client_role_matches_candidate_role(client, applied_role):
            relevant_clients.append(client)

    return relevant_clients[:max_clients]


def extract_json_from_ai_response(response_text):
    if not response_text:
        return None

    cleaned = str(response_text).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)

    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def find_best_client_by_need_match(
    candidate_name,
    applied_role,
    resume_text,
    screening_answers
):
    relevant_clients = get_relevant_clients_for_candidate_role(applied_role)

    if not relevant_clients:
        return None, "", None

    client_blocks = []

    for client in relevant_clients:
        client_id = client[0]
        client_display_name = get_client_display_name(client)
        client_role = client[2] or "Not specified"
        client_location = client[3] or "Not specified"
        client_needs = client[9] or client[4] or ""

        client_blocks.append(
            f"""
CLIENT_ID: {client_id}
CLIENT_NAME: {client_display_name}
CLIENT_ROLE: {client_role}
CLIENT_LOCATION: {client_location}
CLIENT_NEEDS:
{client_needs}
"""
        )

    clients_text = "\n\n---\n\n".join(client_blocks)

    prompt = f"""
You are REPP Talent's client-to-candidate matching assistant.

Your job:
Choose the best client match for this candidate.

Important rules:
- This is NOT location-based matching.
- Match based on client needs, candidate resume, candidate skills, work history, tools, communication style, availability, and screening answers.
- Only choose from the provided clients.
- Do not invent a client.
- If there is no reasonable match, return null for client_id.
- Be strict and practical.

Candidate:
Name: {candidate_name}
Applied Role: {applied_role}

Candidate Resume:
{resume_text if resume_text else "No resume text available."}

Candidate Screening Answers:
{screening_answers if screening_answers else "No screening answers available."}

Available Clients:
{clients_text}

Return only valid JSON in this exact structure:
{{
  "client_id": 123,
  "client_name": "Client Name",
  "match_score": 0.0,
  "reason": "Brief reason for match"
}}

If no reasonable match:
{{
  "client_id": null,
  "client_name": "",
  "match_score": 0.0,
  "reason": "No reasonable match found"
}}
"""

    ai_response = ask_ai(prompt)
    parsed = extract_json_from_ai_response(ai_response)

    if not parsed:
        return None, "", None

    selected_client_id = parsed.get("client_id")
    match_score = safe_float(parsed.get("match_score"))

    if not selected_client_id:
        return None, "", None

    for client in relevant_clients:
        if str(client[0]) == str(selected_client_id):
            return client[0], get_client_display_name(client), match_score

    return None, "", None


def find_best_client_match_for_candidate_data(
    candidate_name,
    candidate_location,
    applied_role,
    resume_text,
    screening_answers
):
    if role_uses_ai_need_matching(applied_role):
        return find_best_client_by_need_match(
            candidate_name=candidate_name,
            applied_role=applied_role,
            resume_text=resume_text,
            screening_answers=screening_answers
        )

    return find_nearest_client(candidate_location)


def find_best_client_match_from_candidate(candidate):
    candidate_name = candidate[1] or ""
    candidate_location = candidate[2] or ""
    applied_role = candidate[3] or ""
    resume_text = candidate[4] or ""
    screening_answers = candidate[5] or ""

    return find_best_client_match_for_candidate_data(
        candidate_name=candidate_name,
        candidate_location=candidate_location,
        applied_role=applied_role,
        resume_text=resume_text,
        screening_answers=screening_answers
    )


# -----------------------------
# RESUME HELPERS
# -----------------------------

def candidate_has_resume(candidate):
    resume_text = candidate[4] or ""

    if not resume_text.strip():
        return False

    if "no readable resume text could be extracted" in resume_text.lower():
        return False

    return True


def show_missing_resume_banner():
    st.error("Please Upload the candidate's Resume")


def parse_uploaded_resume_file(uploaded_file):
    if not uploaded_file:
        return ""

    os.makedirs("uploads", exist_ok=True)

    safe_file_name = uploaded_file.name.replace("/", "_").replace("\\", "_")
    file_path = os.path.join("uploads", safe_file_name)

    with open(file_path, "wb") as file:
        file.write(uploaded_file.getbuffer())

    file_type = safe_file_name.split(".")[-1].lower()

    parsed_text = extract_resume_text(file_path, file_type)

    if not parsed_text.strip():
        return """
No readable resume text could be extracted from this file.

Please upload a clearer PDF, DOCX, TXT, PNG, JPG, or JPEG resume.
If this is an image resume, make sure OCR dependencies are installed.
"""

    return parsed_text


def create_resume_summary(candidate):
    candidate_name = candidate[1] or "Unnamed Candidate"
    applied_role = candidate[3] or "Not specified"
    resume_text = candidate[4] or ""

    prompt = f"""
You are REPP Talent's resume parsing assistant.

Extract and organize the candidate resume information for recruiting use.

Focus only on information found in the resume.
Do not invent facts.
Do not overpraise.

Candidate Name:
{candidate_name}

Role Applied:
{applied_role}

Resume Text:
{resume_text}

Return the parsed resume in this structure:

WORK HISTORY
- Company:
- Role:
- Dates:
- Responsibilities:
- Relevant achievements:

EDUCATION
- School:
- Degree / Program:
- Dates if available:

ACHIEVEMENTS / CERTIFICATIONS
- List achievements, certifications, licenses, tools, platforms, awards, or measurable wins.

RECRUITING SIGNALS
- Relevant experience for the applied role:
- Client-facing or communication experience:
- Reliability / ownership signals:
- Risks or gaps visible from the resume:

SHORT RESUME SUMMARY
- 4 to 6 sentence practical summary for recruiter use.
"""

    return ask_ai(prompt)


def create_short_summary(candidate):
    candidate_name = candidate[1] or "Unnamed Candidate"
    applied_role = candidate[3] or "Not specified"
    resume_text = candidate[4] or ""
    screening_answers = candidate[5] or ""
    candidate_status = candidate[10] or "Prospects"
    matched_client_name = candidate[12] or "No mapped client"

    prompt = f"""
You are REPP Talent's candidate summary assistant.

Create a concise recruiter-facing short summary based on the candidate resume and screening answers.

Rules:
- Do not overpraise.
- Do not invent facts.
- Mention role fit, relevant experience, availability, communication/client-facing fit, and risks if visible.
- Focus especially on work history, education, achievements, and role alignment.
- Keep it practical for a recruiter.

Candidate Name:
{candidate_name}

Role Applied:
{applied_role}

Current Status:
{candidate_status}

Mapped Client:
{matched_client_name}

Resume:
{resume_text}

Screening Answers:
{screening_answers}

Return only the short summary in 4 to 6 sentences.
"""

    return ask_ai(prompt)


def build_screening_answers_from_row(row, applied_role):
    role = normalize_text(applied_role)

    if role == "photographer":
        columns = PHOTOGRAPHER_SCREENING_COLUMNS
    elif role == "va":
        columns = VA_SCREENING_COLUMNS
    elif role == "real estate media":
        columns = REAL_ESTATE_MEDIA_ADMIN_SCREENING_COLUMNS
    else:
        columns = (
            PHOTOGRAPHER_SCREENING_COLUMNS
            + VA_SCREENING_COLUMNS
            + REAL_ESTATE_MEDIA_ADMIN_SCREENING_COLUMNS
        )

    answers = []

    general_screener_answers = (
        safe_value(row, "Screener  Answers")
        or safe_value(row, "Screener Answers")
    )

    if general_screener_answers:
        answers.append(f"Screener Answers\nAnswer: {general_screener_answers}")

    initial_thoughts = safe_value(row, "Initial Thoughts")
    if initial_thoughts:
        answers.append(f"Initial Thoughts\nAnswer: {initial_thoughts}")

    impression = safe_value(row, "Impression")
    if impression:
        answers.append(f"Impression\nAnswer: {impression}")

    recording_review = safe_value(row, "Recording Review")
    if recording_review:
        answers.append(f"Recording Review\nAnswer: {recording_review}")

    leesa_final_thoughts = safe_value(row, "Leesa Final Thoughts")
    if leesa_final_thoughts:
        answers.append(f"Leesa Final Thoughts\nAnswer: {leesa_final_thoughts}")

    age_confirmed = safe_value(row, "Are you 18+")
    if age_confirmed:
        answers.append(f"Are you 18+\nAnswer: {age_confirmed}")

    for column in columns:
        answer = safe_value(row, column)

        if answer:
            answers.append(f"{column}\nAnswer: {answer}")

    return "\n\n".join(answers)


def get_mapped_client(candidate):
    matched_client_id = candidate[11] if len(candidate) > 11 else None
    matched_client_name = candidate[12] if len(candidate) > 12 else ""
    matched_distance = candidate[13] if len(candidate) > 13 else None

    return matched_client_id, matched_client_name, matched_distance


def build_client_notes_from_row(row):
    name = safe_value(row, "Name")
    company_name = safe_value(row, "Company Name")
    email = safe_value(row, "What is your email address?")
    monday_doc = safe_value(row, "monday Doc")
    role = safe_value(row, "What Role Are You Hiring?")
    ideal_location = safe_value(row, "What would be the ideal location for the hire?")
    compensation_type = safe_value(row, "Compensation Type")
    compensation_details = safe_value(row, "Compensation Details")
    gear_provided = safe_value(row, "Is Gear Provided by The Company?")
    employment_type = safe_value(row, "Employment Type")
    hours_per_week = safe_value(row, "How Many Hours Per Week Will This Employee Work?")
    availability_requirements = safe_value(row, "Any Specific Availability Requirements?")
    character_traits = safe_value(row, "What kind of character traits or values do you believe are essential for someone to thrive on your team?")
    anything_else = safe_value(row, "Anything else we should know?")
    hiring_radius = safe_value(row, "Hiring Radius")
    green_or_experienced = safe_value(row, "Green or Experienced?")
    service_radius = safe_value(row, "Service Radius")
    urgency = safe_value(row, "Urgency")

    # Save and display the actual client/contact name first.
    # Company name is only a fallback if the contact/client name is blank.
    client_display_name = name or company_name or "Unnamed Client"
    client_location = ideal_location or "Not specified"

    raw_notes = f"""
Client Name:
{client_display_name}

Contact Name:
{name if name else "Not specified"}

Company Name:
{company_name if company_name else "Not specified"}

Email:
{email if email else "Not specified"}

Monday Doc:
{monday_doc if monday_doc else "Not specified"}

Role Hiring:
{role if role else "Not specified"}

Ideal Location for Hire:
{ideal_location if ideal_location else "Not specified"}

Compensation Type:
{compensation_type if compensation_type else "Not specified"}

Compensation Details:
{compensation_details if compensation_details else "Not specified"}

Is Gear Provided by the Company:
{gear_provided if gear_provided else "Not specified"}

Employment Type:
{employment_type if employment_type else "Not specified"}

Hours Per Week:
{hours_per_week if hours_per_week else "Not specified"}

Specific Availability Requirements:
{availability_requirements if availability_requirements else "Not specified"}

Essential Character Traits / Values:
{character_traits if character_traits else "Not specified"}

Anything Else We Should Know:
{anything_else if anything_else else "Not specified"}

Hiring Radius:
{hiring_radius if hiring_radius else "Not specified"}

Green or Experienced:
{green_or_experienced if green_or_experienced else "Not specified"}

Service Radius:
{service_radius if service_radius else "Not specified"}

Urgency:
{urgency if urgency else "Not specified"}
"""

    return client_display_name, client_location, role, raw_notes


# -----------------------------
# LOGIN GATE
# -----------------------------

require_app_login()


# -----------------------------
# TOP TABS
# -----------------------------

st.markdown("## AI Hiring Engine")

if is_admin_user():
    top_tabs = st.tabs(["Dashboard", "Candidates", "Admin Center"])
    dashboard_tab = top_tabs[0]
    candidates_tab = top_tabs[1]
    admin_center_tab = top_tabs[2]
else:
    top_tabs = st.tabs(["Dashboard", "Candidates"])
    dashboard_tab = top_tabs[0]
    candidates_tab = top_tabs[1]
    admin_center_tab = None

logout_button()
st.divider()


# -----------------------------
# DASHBOARD
# -----------------------------

with dashboard_tab:
    st.header("Dashboard")

    counts = count_records()

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Candidates", f"{counts.get('candidates', 0):,}")
    col2.metric("Clients", f"{counts.get('clients', 0):,}")
    col3.metric("Screenings", f"{counts.get('screening_results', 0):,}")
    col4.metric("Scripts", f"{counts.get('interview_scripts', 0):,}")
    col5.metric("Evaluations", f"{counts.get('evaluations', 0):,}")

    st.success("Dashboard is optimized. It uses database counts only and does not load all candidate records.")


# -----------------------------
# CANDIDATES
# -----------------------------

with candidates_tab:
    st.header("Candidates")

    if "selected_candidate_profile_id" not in st.session_state:
        st.session_state.selected_candidate_profile_id = None

    if "candidate_search_term" not in st.session_state:
        st.session_state.candidate_search_term = ""

    if "candidate_search_offset" not in st.session_state:
        st.session_state.candidate_search_offset = 0

    if st.session_state.selected_candidate_profile_id is None:
        st.subheader("Search Candidate")

        col_search, col_status, col_role = st.columns([2, 1, 1])

        with col_search:
            search_term = st.text_input(
                "Search Candidate",
                placeholder="Name, email, phone, city, role, status, or mapped client",
                value=st.session_state.candidate_search_term,
                key="candidate_search_input"
            )

        with col_status:
            status_filter = st.selectbox(
                "Status Filter",
                [""] + CANDIDATE_STATUS_OPTIONS,
                key="candidate_status_filter"
            )

        with col_role:
            role_filter = st.selectbox(
                "Role Filter",
                APPLIED_ROLE_OPTIONS,
                key="candidate_role_filter"
            )

        col_a, col_b = st.columns([1, 1])

        with col_a:
            if st.button("Search", use_container_width=True):
                st.session_state.candidate_search_term = search_term
                st.session_state.candidate_search_offset = 0
                st.rerun()

        with col_b:
            if st.button("Clear Search", use_container_width=True):
                st.session_state.candidate_search_term = ""
                st.session_state.candidate_search_offset = 0
                st.rerun()

        limit = 25
        offset = st.session_state.candidate_search_offset

        candidates = search_candidates(
            search_term=st.session_state.candidate_search_term,
            status_filter=status_filter,
            role_filter=role_filter,
            limit=limit,
            offset=offset
        )

        st.caption(
            f"Showing up to {limit} results. This search is database-powered for low-end PC performance."
        )

        if not candidates:
            st.info("No candidates found. Search by name, email, phone, role, status, city, or mapped client.")
        else:
            for candidate in candidates:
                candidate_id = candidate[0]
                candidate_name = candidate[1] or "Unnamed Candidate"
                candidate_location = candidate[2] or "No Location"
                applied_role = candidate[3] or "No Role"
                candidate_status = candidate[10] or "No Status"
                matched_client = candidate[12] or "No Client"
                matched_value = candidate[13]

                with st.container(border=True):
                    col_info, col_action = st.columns([4, 1])

                    with col_info:
                        st.markdown(f"### {candidate_name}")
                        st.write(f"**Role:** {applied_role}")
                        st.write(f"**Status:** {candidate_status}")
                        st.write(f"**Location:** {candidate_location}")
                        st.write(f"**Mapped Client:** {matched_client}")

                        if matched_value is not None and matched_value != "":
                            if role_uses_ai_need_matching(applied_role):
                                st.write(f"**Need Match Score:** {matched_value}")
                            else:
                                st.write(f"**Distance:** {matched_value} miles")

                        if not candidate_has_resume(candidate):
                            st.error("Missing Resume")

                    with col_action:
                        if st.button("Open", key=f"open_candidate_{candidate_id}", use_container_width=True):
                            st.session_state.selected_candidate_profile_id = candidate_id
                            st.rerun()

            col_prev, col_next = st.columns(2)

            with col_prev:
                if offset > 0:
                    if st.button("Previous 25", use_container_width=True):
                        st.session_state.candidate_search_offset = max(0, offset - limit)
                        st.rerun()

            with col_next:
                if len(candidates) == limit:
                    if st.button("Next 25", use_container_width=True):
                        st.session_state.candidate_search_offset = offset + limit
                        st.rerun()

    else:
        candidate_id = st.session_state.selected_candidate_profile_id
        candidate = get_candidate(candidate_id)

        if not candidate:
            st.error("Candidate not found.")

            if st.button("← Back to Candidate Search"):
                st.session_state.selected_candidate_profile_id = None
                st.rerun()

        else:
            if st.button("← Back to Candidate Search"):
                st.session_state.selected_candidate_profile_id = None
                st.rerun()

            st.divider()

            candidate_name = candidate[1] or "Unnamed Candidate"
            candidate_location = candidate[2] or "Not specified"
            applied_role = candidate[3] or "Not specified"
            candidate_status = candidate[10] or "Prospects"
            matched_client_id, matched_client_name, matched_value = get_mapped_client(candidate)
            candidate_extra = get_candidate_extra(candidate_id)

            st.header(candidate_name)

            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**Name:** {candidate_name}")
                st.write(f"**Role Applied:** {applied_role}")
                st.write(f"**Current Status:** {candidate_status}")
                st.write(f"**Location:** {candidate_location}")
                st.write(f"**Email:** {candidate[8] or 'Not specified'}")
                st.write(f"**Phone:** {candidate[9] or 'Not specified'}")

            with col2:
                st.write(f"**Mapped Client:** {matched_client_name if matched_client_name else 'No mapped client'}")

                if matched_value is not None and matched_value != "":
                    if role_uses_ai_need_matching(applied_role):
                        st.write(f"**Need Match Score:** {matched_value}")
                    else:
                        st.write(f"**Distance:** {matched_value} miles")

                if st.button("Map Best Client for This Candidate"):
                    if role_uses_ai_need_matching(applied_role) and not candidate_has_resume(candidate):
                        show_missing_resume_banner()
                    else:
                        with st.spinner("Finding best client match..."):
                            new_client_id, new_client_name, new_value = find_best_client_match_from_candidate(candidate)

                            if new_client_id:
                                update_candidate(
                                    candidate_id=candidate_id,
                                    candidate_name=candidate[1],
                                    email=candidate[8],
                                    phone=candidate[9],
                                    location=candidate[2],
                                    applied_role=candidate[3],
                                    resume_text=candidate[4],
                                    screening_answers=candidate[5],
                                    portfolio_links=candidate[6],
                                    candidate_status=candidate[10],
                                    matched_client_id=new_client_id,
                                    matched_client_name=new_client_name,
                                    matched_client_distance_miles=new_value
                                )

                                if role_uses_ai_need_matching(applied_role):
                                    st.success(f"Mapped to {new_client_name} by client-need match.")
                                else:
                                    st.success(f"Mapped to {new_client_name} | {new_value} miles")

                                st.rerun()
                            else:
                                st.warning("No client match found.")

            st.divider()

            st.subheader("Resume")

            has_resume = candidate_has_resume(candidate)

            if has_resume:
                st.success("Resume is uploaded and parsed.")

                with st.expander("View Resume Text", expanded=False):
                    st.write(candidate[4] or "")

                if st.button("Parse Resume with AI", key=f"parse_resume_ai_{candidate_id}"):
                    with st.spinner("Parsing resume with AI..."):
                        parsed_resume_summary = create_resume_summary(candidate)
                        update_candidate_extra(candidate_id, {"short_summary": parsed_resume_summary})
                        st.success("Resume parsed and saved into Short Summary.")
                        st.rerun()

            else:
                show_missing_resume_banner()

                uploaded_resume = st.file_uploader(
                    "Upload Resume",
                    type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
                    key=f"profile_resume_upload_{candidate_id}"
                )

                if uploaded_resume:
                    if st.button("Upload and Parse Resume", key=f"profile_parse_resume_{candidate_id}"):
                        with st.spinner("Uploading and parsing resume..."):
                            parsed_resume_text = parse_uploaded_resume_file(uploaded_resume)

                            update_candidate(
                                candidate_id=candidate_id,
                                candidate_name=candidate[1],
                                email=candidate[8],
                                phone=candidate[9],
                                location=candidate[2],
                                applied_role=candidate[3],
                                resume_text=parsed_resume_text,
                                screening_answers=candidate[5],
                                portfolio_links=candidate[6],
                                candidate_status=candidate[10],
                                matched_client_id=candidate[11],
                                matched_client_name=candidate[12],
                                matched_client_distance_miles=candidate[13]
                            )

                            refreshed_candidate = get_candidate(candidate_id)

                            if refreshed_candidate and candidate_has_resume(refreshed_candidate):
                                parsed_resume_summary = create_resume_summary(refreshed_candidate)
                                update_candidate_extra(candidate_id, {"short_summary": parsed_resume_summary})

                            st.success("Resume uploaded and parsed.")
                            st.rerun()

            st.divider()

            st.subheader("Short Summary")

            saved_summary = candidate_extra.get("short_summary", "")

            if saved_summary:
                st.write(saved_summary)
            else:
                st.info("No short summary saved yet.")

            if st.button("Generate / Refresh Short Summary", key=f"summary_{candidate_id}"):
                if not candidate_has_resume(candidate):
                    show_missing_resume_banner()
                else:
                    with st.spinner("Generating short summary..."):
                        short_summary = create_short_summary(candidate)
                        update_candidate_extra(candidate_id, {"short_summary": short_summary})
                        st.success("Short summary saved.")
                        st.rerun()

            st.divider()

            if candidate_status == "Initial Interview":
                st.subheader("Scheduled Interview")

                st.write(f"**Interview Date:** {candidate_extra.get('interview_date') or 'Not specified'}")
                st.write(f"**Interviewer:** {candidate_extra.get('interviewer') or 'Not specified'}")

                st.divider()

            if is_read_only_candidate(candidate_status):
                st.info("This candidate is read-only based on their current status.")

            if can_screen_candidate(candidate_status):
                with st.expander("Screen Candidate", expanded=False):
                    if matched_client_id:
                        client = get_client(matched_client_id)
                    else:
                        client = None

                    if client:
                        st.write(f"Screening against client: {get_client_display_name(client)}")
                    else:
                        st.warning("No mapped client found. Screening cannot run accurately.")

                    if st.button("Run Candidate Screening", key=f"screen_candidate_{candidate_id}"):
                        if not candidate_has_resume(candidate):
                            show_missing_resume_banner()
                        elif not client:
                            st.error("Cannot screen because no mapped client is available.")
                        else:
                            with st.spinner("Running screening..."):
                                enhanced_prompt = f"""
{screening_prompt(candidate, client)}

Important:
Use the resume heavily.
Focus on:
- Work history
- Education
- Achievements
- Role alignment
- Client-facing experience
- Reliability signs
- Risks, gaps, or mismatches

Do not overpraise.
Make a real recruiting decision.
"""
                                screening_result = ask_ai(enhanced_prompt)

                                save_screening_result(candidate_id, matched_client_id, screening_result)
                                update_candidate_extra(candidate_id, {"latest_screening_result": screening_result})

                                st.subheader("Screening Result")
                                st.write(screening_result)

            if can_interview_candidate(candidate_status):
                with st.expander("Create Interview Script", expanded=False):
                    if matched_client_id:
                        client = get_client(matched_client_id)
                    else:
                        client = None

                    if client:
                        st.write(f"Creating script for client: {get_client_display_name(client)}")
                    else:
                        st.warning("No mapped client found. Script cannot run accurately.")

                    latest_screening_result = candidate_extra.get("latest_screening_result", "")

                    if st.button("Create Interview Script", key=f"create_script_{candidate_id}"):
                        if not candidate_has_resume(candidate):
                            show_missing_resume_banner()
                        elif not client:
                            st.error("Cannot create script because no mapped client is available.")
                        else:
                            with st.spinner("Creating interview script..."):
                                base_script_prompt = interview_script_prompt(candidate, client)

                                tailored_prompt = f"""
{base_script_prompt}

Additional screening concerns / questionables:
{latest_screening_result if latest_screening_result else "No saved screening result found."}

Important:
Tailor the interview script based on:
- Candidate resume, especially work history, education, and achievements
- Candidate screening answers
- Any questionable or risky areas from screening
- Client needs
- REPP interview standards

Do not ask generic questions only.
Ask role-specific questions that validate fit and expose risks.
"""

                                script = ask_ai(tailored_prompt)

                                save_interview_script(candidate_id, matched_client_id, script)
                                update_candidate_extra(candidate_id, {"latest_interview_script": script})

                                st.subheader("Interview Script")
                                st.write(script)

                with st.expander("Evaluate Interview", expanded=False):
                    transcript_text = st.text_area(
                        "Paste Transcript Manually",
                        height=250,
                        key=f"manual_transcript_{candidate_id}"
                    )

                    transcript_file = st.file_uploader(
                        "Or upload .txt transcript",
                        type=["txt"],
                        key=f"transcript_upload_{candidate_id}"
                    )

                    if transcript_file:
                        transcript_text = transcript_file.read().decode("utf-8", errors="ignore")

                    if st.button("Evaluate Candidate", key=f"evaluate_candidate_{candidate_id}"):
                        if not candidate_has_resume(candidate):
                            show_missing_resume_banner()
                        elif not transcript_text.strip():
                            st.error("Please paste or upload a transcript first.")
                        else:
                            if matched_client_id:
                                client = get_client(matched_client_id)
                            else:
                                client = None

                            if not client:
                                st.error("Cannot evaluate because no mapped client is available.")
                            else:
                                with st.spinner("Evaluating interview..."):
                                    enhanced_evaluation_prompt = f"""
{evaluation_prompt(candidate, client, transcript_text)}

Important:
Evaluate the candidate using:
- Client needs
- Interview transcript
- Resume work history
- Resume education
- Resume achievements
- Screening answers
- Any visible risks, gaps, inconsistencies, or misalignment

Do not overpraise.
Make a real recruiting decision.
"""

                                    evaluation = ask_ai(enhanced_evaluation_prompt)

                                    save_evaluation(candidate_id, matched_client_id, transcript_text, evaluation)
                                    update_candidate_extra(candidate_id, {"latest_evaluation": evaluation})

                                    st.subheader("Evaluation")
                                    st.write(evaluation)


# -----------------------------
# ADMIN CENTER
# -----------------------------

if admin_center_tab is not None:
    with admin_center_tab:
        require_admin()

        st.header("Admin Center")

        admin_tabs = st.tabs([
            "Overview",
            "Add Client",
            "Add Candidate",
            "Manage Clients",
            "Manage Candidates",
            "Command Console"
        ])

        with admin_tabs[0]:
            st.subheader("Admin Overview")

            counts = count_records()

            col1, col2, col3, col4, col5 = st.columns(5)

            col1.metric("Clients", f"{counts.get('clients', 0):,}")
            col2.metric("Candidates", f"{counts.get('candidates', 0):,}")
            col3.metric("Screenings", f"{counts.get('screening_results', 0):,}")
            col4.metric("Scripts", f"{counts.get('interview_scripts', 0):,}")
            col5.metric("Evaluations", f"{counts.get('evaluations', 0):,}")

            st.info("Optimized: this overview uses counts only, not full-table loading.")

        with admin_tabs[1]:
            st.subheader("Add Client")

            client_add_tabs = st.tabs(["Single Client", "Mass Upload Clients"])

            with client_add_tabs[0]:
                client_name = st.text_input("Client / Contact Name", key="admin_single_client_name")
                company_name = st.text_input("Company Name", key="admin_single_company_name")
                location = st.text_input("Client Location / Geo Location", key="admin_single_client_location")
                role = st.text_input("Role", value="Not specified", key="admin_single_client_role")
                client_needs = st.text_area("Client Needs", height=250, key="admin_single_client_needs")

                if "admin_formatted_client_needs" not in st.session_state:
                    st.session_state.admin_formatted_client_needs = ""

                if st.button("Format Client Needs", key="admin_format_client"):
                    if not client_needs.strip():
                        st.error("Please paste client needs first.")
                    else:
                        raw_client_notes = f"""
Client Name:
{client_name if client_name else "Not specified"}

Contact Name:
{client_name if client_name else "Not specified"}

Company Name:
{company_name if company_name else "Not specified"}

Role Hiring:
{role if role else "Not specified"}

Ideal Location for Hire:
{location if location else "Not specified"}

Client Needs:
{client_needs}
"""
                        with st.spinner("Formatting client needs..."):
                            prompt = client_formatter_prompt(raw_client_notes)
                            formatted_details = ask_ai(prompt)
                            st.session_state.admin_formatted_client_needs = formatted_details
                        st.success("Client needs formatted.")

                formatted_client_needs = st.text_area(
                    "Formatted Client Needs",
                    value=st.session_state.admin_formatted_client_needs,
                    height=300,
                    key="admin_single_formatted_client_needs"
                )

                if st.button("Submit Client", key="admin_submit_client"):
                    if not client_name.strip():
                        st.error("Please enter client/contact name.")
                    elif not location.strip():
                        st.error("Please enter client location.")
                    elif client_duplicate_exists(client_name, location):
                        st.warning("Duplicate client found. Client was not uploaded.")
                    else:
                        final_notes = formatted_client_needs or f"""
Client Name:
{client_name}

Contact Name:
{client_name}

Company Name:
{company_name if company_name else "Not specified"}

Role Hiring:
{role if role else "Not specified"}

Ideal Location for Hire:
{location if location else "Not specified"}

Client Needs:
{client_needs}
"""

                        client_display_name_for_save = client_name.strip() or company_name.strip() or "Unnamed Client"

                        client_id = add_client(
                            client_display_name_for_save,
                            role or "Not specified",
                            location,
                            final_notes,
                            formatted_client_needs=final_notes
                        )

                        if client_id:
                            st.success(f"Client saved. Client ID: {client_id}")
                            st.session_state.admin_formatted_client_needs = ""
                        else:
                            st.error("Client was not saved.")

            with client_add_tabs[1]:
                uploaded_csv = st.file_uploader(
                    "Upload Client CSV",
                    type=["csv"],
                    key="admin_client_csv_upload"
                )

                if uploaded_csv:
                    try:
                        df = pd.read_csv(uploaded_csv)
                    except UnicodeDecodeError:
                        uploaded_csv.seek(0)
                        df = pd.read_csv(uploaded_csv, encoding="latin-1")

                    df = clean_dataframe_columns(df)

                    st.write(f"Total rows found: {len(df):,}")
                    st.caption("Low-end mode: showing first 20 rows only.")
                    st.dataframe(df.head(20), use_container_width=True, height=350)

                    max_rows = st.number_input(
                        "How many rows do you want to import?",
                        min_value=1,
                        max_value=len(df),
                        value=len(df),
                        step=1,
                        key="admin_client_import_max_rows"
                    )

                    start_row = st.number_input(
                        "Start from row number",
                        min_value=1,
                        max_value=len(df),
                        value=1,
                        step=1,
                        key="admin_client_import_start_row"
                    )

                    use_ai_formatting = st.checkbox(
                        "Use AI to format client needs during import",
                        value=False,
                        key="use_ai_client_formatting_import"
                    )

                    st.caption("For large imports, keep AI formatting unchecked. You can format individual clients later.")

                    if st.button("Import Clients from CSV", key="admin_import_clients_csv"):
                        imported_count = 0
                        skipped_duplicates = []
                        skipped_blank_rows = []
                        skipped_header_rows = []
                        failed_rows = []

                        progress_bar = st.progress(0)
                        status_box = st.empty()

                        start_index = int(start_row) - 1
                        end_index = min(start_index + int(max_rows), len(df))
                        import_df = df.iloc[start_index:end_index]

                        for processed_number, (index, row) in enumerate(import_df.iterrows(), start=1):
                            row_number = index + 1

                            try:
                                if row_is_fully_blank(row):
                                    skipped_blank_rows.append(build_failure(row_number, "Full blank row", row))
                                    progress_bar.progress(processed_number / max(1, len(import_df)))
                                    continue

                                if row_looks_like_header(row):
                                    skipped_header_rows.append(build_failure(row_number, "Possible repeated header row", row))
                                    progress_bar.progress(processed_number / max(1, len(import_df)))
                                    continue

                                client_display_name, client_location, role, raw_notes = build_client_notes_from_row(row)

                                if client_duplicate_exists(client_display_name, client_location):
                                    skipped_duplicates.append(
                                        build_failure(
                                            row_number,
                                            "Duplicate client name and location",
                                            row,
                                            {"client": client_display_name, "location": client_location}
                                        )
                                    )
                                else:
                                    status_box.write(f"Importing row {row_number}: {client_display_name}")

                                    if use_ai_formatting:
                                        formatted_details = ask_ai(client_formatter_prompt(raw_notes))
                                    else:
                                        formatted_details = raw_notes

                                    client_id = add_client(
                                        client_display_name,
                                        role if role else "Not specified",
                                        client_location,
                                        formatted_details,
                                        formatted_client_needs=formatted_details
                                    )

                                    if not client_id:
                                        failed_rows.append(
                                            build_failure(
                                                row_number,
                                                "Supabase insert failed or returned no client ID",
                                                row,
                                                {"client": client_display_name, "location": client_location}
                                            )
                                        )
                                    else:
                                        imported_count += 1

                            except Exception as error:
                                failed_rows.append(
                                    build_failure(
                                        row_number,
                                        "Unexpected import error",
                                        row,
                                        {"error": str(error)}
                                    )
                                )

                            progress_bar.progress(min(processed_number / max(1, len(import_df)), 1.0))

                        st.success(f"Import complete. Imported {imported_count:,} clients.")

                        if skipped_blank_rows:
                            st.warning(f"Skipped {len(skipped_blank_rows):,} blank rows.")
                            st.write(skipped_blank_rows[:20])

                        if skipped_header_rows:
                            st.warning(f"Skipped {len(skipped_header_rows):,} possible header rows.")
                            st.write(skipped_header_rows[:20])

                        if skipped_duplicates:
                            st.warning(f"Skipped {len(skipped_duplicates):,} duplicate clients.")
                            st.write(skipped_duplicates[:20])

                        if failed_rows:
                            st.error(f"{len(failed_rows):,} rows failed.")
                            st.write(failed_rows[:20])

        with admin_tabs[2]:
            st.subheader("Add Candidate")

            candidate_add_tabs = st.tabs(["Single Candidate", "Mass Upload Candidates"])

            with candidate_add_tabs[0]:
                candidate_name = st.text_input("Candidate Name", key="admin_candidate_name")
                email = st.text_input("Email", key="admin_candidate_email")
                phone = st.text_input("Phone", key="admin_candidate_phone")
                location = st.text_input("Candidate Location / Geo Location", key="admin_candidate_location")

                applied_role = st.selectbox(
                    "Applied Role",
                    APPLIED_ROLE_OPTIONS,
                    key="admin_candidate_role"
                )

                candidate_status = st.selectbox(
                    "Candidate Category",
                    CANDIDATE_STATUS_OPTIONS,
                    key="admin_candidate_status"
                )

                screening_answers = st.text_area(
                    "Screening Questions and Answers",
                    height=220,
                    key="admin_candidate_screening_answers"
                )

                resume_file = st.file_uploader(
                    "Upload Resume",
                    type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
                    key="admin_candidate_resume_upload"
                )

                map_best_client_now = st.checkbox(
                    "Map best client now",
                    value=False,
                    key="single_candidate_best_client_mapping"
                )

                resume_text_for_save = ""

                if resume_file:
                    resume_text_for_save = parse_uploaded_resume_file(resume_file)

                if map_best_client_now:
                    if role_uses_ai_need_matching(applied_role) and not resume_text_for_save:
                        matched_client_id, matched_client_name, matched_value = None, "", None
                        st.warning("Upload a resume first to use AI need-based matching for this role.")
                    else:
                        matched_client_id, matched_client_name, matched_value = find_best_client_match_for_candidate_data(
                            candidate_name=candidate_name,
                            candidate_location=location,
                            applied_role=applied_role,
                            resume_text=resume_text_for_save,
                            screening_answers=screening_answers
                        )

                        if matched_client_name:
                            if role_uses_ai_need_matching(applied_role):
                                st.info(f"Best Client Match: {matched_client_name} | Need Match Score: {matched_value}")
                            else:
                                st.info(f"Nearest Client Match: {matched_client_name} | {matched_value} miles")
                        else:
                            matched_client_id, matched_client_name, matched_value = None, "", None
                            st.warning("No client match found.")
                else:
                    matched_client_id, matched_client_name, matched_value = None, "", None

                interview_date = st.text_input("Interview Date", key="admin_candidate_interview_date")
                interviewer = st.selectbox("Interviewer", INTERVIEWER_OPTIONS, key="admin_candidate_interviewer")

                if st.button("Save Candidate", key="admin_save_single_candidate"):
                    if not candidate_name.strip():
                        st.error("Please enter candidate name.")
                    elif not location.strip():
                        st.error("Please enter candidate location.")
                    elif candidate_duplicate_exists(candidate_name, location, applied_role):
                        st.warning("Duplicate candidate found. Candidate was not uploaded.")
                    else:
                        candidate_id = add_candidate(
                            candidate_name=candidate_name,
                            email=email,
                            phone=phone,
                            location=location,
                            applied_role=applied_role,
                            resume_text=resume_text_for_save,
                            screening_answers=screening_answers,
                            portfolio_links="",
                            candidate_status=candidate_status,
                            matched_client_id=matched_client_id,
                            matched_client_name=matched_client_name,
                            matched_client_distance_miles=matched_value
                        )

                        if candidate_id:
                            update_candidate_extra(
                                candidate_id,
                                {
                                    "interview_date": interview_date,
                                    "interviewer": interviewer
                                }
                            )

                            refreshed_candidate = get_candidate(candidate_id)

                            if refreshed_candidate and candidate_has_resume(refreshed_candidate):
                                parsed_resume_summary = create_resume_summary(refreshed_candidate)
                                update_candidate_extra(candidate_id, {"short_summary": parsed_resume_summary})

                            st.success(f"Candidate saved. Candidate ID: {candidate_id}")
                        else:
                            st.error("Candidate was not saved.")

            with candidate_add_tabs[1]:
                st.info("Low-end optimized import: first 20-row preview only, skip client mapping by default, no AI auto-processing.")

                uploaded_candidate_csv = st.file_uploader(
                    "Upload Candidate CSV",
                    type=["csv"],
                    key="admin_candidate_csv_upload"
                )

                default_status_for_import = st.selectbox(
                    "Default Candidate Category",
                    CANDIDATE_STATUS_OPTIONS,
                    key="admin_mass_candidate_default_status"
                )

                skip_mapping_for_import = st.checkbox(
                    "Skip client mapping during mass import for faster upload",
                    value=True,
                    key="skip_client_mapping_for_candidate_import"
                )

                if uploaded_candidate_csv:
                    try:
                        df = pd.read_csv(uploaded_candidate_csv)
                    except UnicodeDecodeError:
                        uploaded_candidate_csv.seek(0)
                        df = pd.read_csv(uploaded_candidate_csv, encoding="latin-1")

                    df = clean_dataframe_columns(df)

                    st.write(f"Total rows found: {len(df):,}")
                    st.caption("Low-end mode: showing first 20 rows only.")
                    st.dataframe(df.head(20), use_container_width=True, height=350)

                    with st.expander("Detected CSV Headers"):
                        st.write(list(df.columns))

                    max_rows = st.number_input(
                        "How many rows do you want to import?",
                        min_value=1,
                        max_value=len(df),
                        value=len(df),
                        step=1,
                        key="admin_candidate_import_max_rows"
                    )

                    start_row = st.number_input(
                        "Start from row number",
                        min_value=1,
                        max_value=len(df),
                        value=1,
                        step=1,
                        key="admin_candidate_import_start_row"
                    )

                    if st.button("Import Candidates from CSV", key="admin_import_candidates_csv"):
                        imported_count = 0
                        skipped_duplicates = []
                        skipped_blank_rows = []
                        skipped_header_rows = []
                        failed_rows = []
                        warning_rows = []

                        progress_bar = st.progress(0)
                        status_box = st.empty()

                        start_index = int(start_row) - 1
                        end_index = min(start_index + int(max_rows), len(df))
                        import_df = df.iloc[start_index:end_index]

                        for processed_number, (index, row) in enumerate(import_df.iterrows(), start=1):
                            row_number = index + 1

                            try:
                                if row_is_fully_blank(row):
                                    skipped_blank_rows.append(build_failure(row_number, "Full blank row", row))
                                    progress_bar.progress(processed_number / max(1, len(import_df)))
                                    continue

                                if row_looks_like_header(row):
                                    skipped_header_rows.append(build_failure(row_number, "Possible repeated header row", row))
                                    progress_bar.progress(processed_number / max(1, len(import_df)))
                                    continue

                                candidate_name = get_first_available_value(
                                    row,
                                    [
                                        "Full Name",
                                        "Name",
                                        "Candidate Name",
                                        "Applicant Name",
                                        "First and Last Name",
                                        "Full name",
                                        "Applicant",
                                        "Candidate",
                                        "Your Name",
                                        "What is your name?",
                                        "What is your full name?"
                                    ]
                                )

                                email = get_first_available_value(
                                    row,
                                    [
                                        "Email",
                                        "Email Address",
                                        "What is your email address?",
                                        "Candidate Email",
                                        "Email address"
                                    ]
                                )

                                phone = get_first_available_value(
                                    row,
                                    [
                                        "Phone",
                                        "Phone Number",
                                        "Mobile Number",
                                        "Candidate Phone",
                                        "Phone number",
                                        "Mobile"
                                    ]
                                )

                                location = get_first_available_value(
                                    row,
                                    [
                                        "Where are you located?",
                                        "We are hiring for multiple locations. Which city is the role you’re interested in?",
                                        "We are hiring for multiple locations. Which city is the role you're interested in?",
                                        "Location",
                                        "Candidate Location",
                                        "City",
                                        "Address",
                                        "Geo Location",
                                        "Candidate Location / Geo Location",
                                        "What is your location?",
                                        "Where are you based?"
                                    ]
                                )

                                raw_role_from_csv = get_first_available_value(
                                    row,
                                    [
                                        "What position are you applying for?",
                                        "What Role Are You Hiring?",
                                        "Applied Role",
                                        "Role",
                                        "Position",
                                        "What Role Are You Applying For?",
                                        "Role Applied For"
                                    ]
                                )

                                applied_role = map_applied_role(raw_role_from_csv)

                                status_from_csv = get_first_available_value(
                                    row,
                                    [
                                        "Stage",
                                        "Status",
                                        "Candidate Status",
                                        "Category"
                                    ]
                                )

                                normalized_status = normalize_candidate_status(status_from_csv)
                                candidate_status = normalized_status if normalized_status else default_status_for_import

                                interview_date = get_first_available_value(row, ["Interview Date", "Leesa Interview Date"])
                                interviewer = get_first_available_value(row, ["Interviewer"])

                                if not candidate_name:
                                    failed_rows.append(
                                        build_failure(
                                            row_number,
                                            "Missing candidate name. Expected Full Name, Name, Candidate Name, or similar.",
                                            row
                                        )
                                    )
                                    continue

                                if not location:
                                    location = "Not specified"
                                    warning_rows.append(
                                        build_failure(
                                            row_number,
                                            "Candidate location was blank. Saved as Not specified.",
                                            row,
                                            {"candidate": candidate_name}
                                        )
                                    )

                                if not applied_role:
                                    warning_rows.append(
                                        build_failure(
                                            row_number,
                                            "Applied role was blank or unrecognized. Recruiter must update manually.",
                                            row,
                                            {"candidate": candidate_name, "raw_role_from_csv": raw_role_from_csv}
                                        )
                                    )

                                screening_answers = build_screening_answers_from_row(row, applied_role)

                                if candidate_duplicate_exists(candidate_name, location, applied_role):
                                    skipped_duplicates.append(
                                        build_failure(
                                            row_number,
                                            "Duplicate candidate name, location, and role",
                                            row,
                                            {
                                                "candidate": candidate_name,
                                                "location": location,
                                                "role": applied_role
                                            }
                                        )
                                    )
                                else:
                                    status_box.write(f"Importing row {row_number}: {candidate_name}")

                                    if skip_mapping_for_import:
                                        matched_client_id = None
                                        matched_client_name = ""
                                        matched_value = None
                                    else:
                                        matched_client_id, matched_client_name, matched_value = find_best_client_match_for_candidate_data(
                                            candidate_name=candidate_name,
                                            candidate_location=location,
                                            applied_role=applied_role,
                                            resume_text="",
                                            screening_answers=screening_answers
                                        )

                                    candidate_id = add_candidate(
                                        candidate_name=candidate_name,
                                        email=email,
                                        phone=phone,
                                        location=location,
                                        applied_role=applied_role,
                                        resume_text="",
                                        screening_answers=screening_answers,
                                        portfolio_links="",
                                        candidate_status=candidate_status,
                                        matched_client_id=matched_client_id,
                                        matched_client_name=matched_client_name,
                                        matched_client_distance_miles=matched_value
                                    )

                                    if not candidate_id:
                                        failed_rows.append(
                                            build_failure(
                                                row_number,
                                                "Supabase insert failed or returned no candidate ID.",
                                                row,
                                                {
                                                    "candidate": candidate_name,
                                                    "location": location,
                                                    "applied_role": applied_role
                                                }
                                            )
                                        )
                                    else:
                                        update_candidate_extra(
                                            candidate_id,
                                            {
                                                "interview_date": interview_date,
                                                "interviewer": interviewer
                                            }
                                        )
                                        imported_count += 1

                            except Exception as error:
                                failed_rows.append(
                                    build_failure(
                                        row_number,
                                        "Unexpected import error",
                                        row,
                                        {"error": str(error)}
                                    )
                                )

                            progress_bar.progress(min(processed_number / max(1, len(import_df)), 1.0))

                        st.success(f"Import complete. Imported {imported_count:,} candidates.")

                        if warning_rows:
                            st.warning(f"{len(warning_rows):,} rows imported or processed with warnings.")
                            st.write(warning_rows[:20])

                        if skipped_blank_rows:
                            st.warning(f"Skipped {len(skipped_blank_rows):,} blank rows.")
                            st.write(skipped_blank_rows[:20])

                        if skipped_header_rows:
                            st.warning(f"Skipped {len(skipped_header_rows):,} possible header rows.")
                            st.write(skipped_header_rows[:20])

                        if skipped_duplicates:
                            st.warning(f"Skipped {len(skipped_duplicates):,} duplicate candidates.")
                            st.write(skipped_duplicates[:20])

                        if failed_rows:
                            st.error(f"{len(failed_rows):,} rows failed.")
                            st.write(failed_rows[:20])

        with admin_tabs[3]:
            st.subheader("Manage Clients")

            client_search = st.text_input("Search Clients", key="admin_client_search")
            clients = search_clients(client_search, limit=50)

            st.caption("Showing up to 50 clients for performance.")

            col_list, col_detail = st.columns([1, 2])

            with col_list:
                for client in clients:
                    client_id = client[0]
                    client_name = get_client_display_name(client) or "Unnamed Client"
                    client_location = client[3] or "No location"

                    if st.button(
                        f"{client_name} | {client_location}",
                        key=f"client_select_{client_id}",
                        use_container_width=True
                    ):
                        st.session_state.selected_admin_client_id = client_id

            with col_detail:
                if "selected_admin_client_id" not in st.session_state:
                    st.info("Select a client from the list.")
                else:
                    selected_client_id = st.session_state.selected_admin_client_id
                    client = get_client(selected_client_id)

                    if not client:
                        st.error("Client not found.")
                    else:
                        edit_client_name = st.text_input(
                            "Client / Contact Name",
                            value=get_client_display_name(client) or client[1] or "",
                            key=f"edit_client_name_{selected_client_id}"
                        )

                        edit_client_location = st.text_input(
                            "Location / Geo Location",
                            value=client[3] or "",
                            key=f"edit_client_location_{selected_client_id}"
                        )

                        edit_client_role = st.text_input(
                            "Role",
                            value=client[2] or "Not specified",
                            key=f"edit_client_role_{selected_client_id}"
                        )

                        edit_formatted_needs = st.text_area(
                            "Formatted Client Needs",
                            value=client[9] or client[4] or "",
                            height=350,
                            key=f"edit_client_needs_{selected_client_id}"
                        )

                        col_save, col_delete = st.columns(2)

                        with col_save:
                            if st.button("Save Client Changes", key=f"save_client_{selected_client_id}"):
                                notes = edit_formatted_needs

                                if "Contact Name:" not in notes:
                                    notes = f"""
Client Name:
{edit_client_name}

Contact Name:
{edit_client_name}

{notes}
"""

                                update_client(
                                    selected_client_id,
                                    edit_client_name,
                                    edit_client_role,
                                    edit_client_location,
                                    notes,
                                    formatted_client_needs=notes
                                )

                                st.success("Client updated.")
                                st.rerun()

                        with col_delete:
                            confirm_delete_client = st.checkbox(
                                "Confirm delete this client.",
                                key=f"confirm_delete_client_{selected_client_id}"
                            )

                            if st.button("Delete Client", key=f"delete_client_{selected_client_id}"):
                                if confirm_delete_client:
                                    delete_client(selected_client_id)

                                    if "selected_admin_client_id" in st.session_state:
                                        del st.session_state.selected_admin_client_id

                                    st.success("Client deleted.")
                                    st.rerun()
                                else:
                                    st.error("Please confirm before deleting.")

        with admin_tabs[4]:
            st.subheader("Manage Candidates")

            col_search, col_status, col_role = st.columns([2, 1, 1])

            with col_search:
                admin_candidate_search = st.text_input("Search Candidates", key="admin_candidate_search")

            with col_status:
                admin_status_filter = st.selectbox(
                    "Status",
                    [""] + CANDIDATE_STATUS_OPTIONS,
                    key="admin_candidate_status_filter"
                )

            with col_role:
                admin_role_filter = st.selectbox(
                    "Role",
                    APPLIED_ROLE_OPTIONS,
                    key="admin_candidate_role_filter"
                )

            candidates = search_candidates(
                search_term=admin_candidate_search,
                status_filter=admin_status_filter,
                role_filter=admin_role_filter,
                limit=50,
                offset=0
            )

            st.caption("Showing up to 50 candidates for performance.")

            col_list, col_detail = st.columns([1, 2])

            with col_list:
                for candidate in candidates:
                    candidate_id = candidate[0]
                    candidate_name = candidate[1] or "Unnamed Candidate"
                    applied_role = candidate[3] or "No role"
                    candidate_status = candidate[10] or "No Status"
                    matched_client = candidate[12] or "No Client"

                    button_label = f"{candidate_name} | {applied_role} | {candidate_status} | {matched_client}"

                    if not candidate_has_resume(candidate):
                        button_label = f"{button_label} | Missing Resume"

                    if st.button(button_label, key=f"candidate_select_{candidate_id}", use_container_width=True):
                        st.session_state.selected_admin_candidate_id = candidate_id

            with col_detail:
                if "selected_admin_candidate_id" not in st.session_state:
                    st.info("Select a candidate from the list.")
                else:
                    selected_candidate_id = st.session_state.selected_admin_candidate_id
                    candidate = get_candidate(selected_candidate_id)

                    if not candidate:
                        st.error("Candidate not found.")
                    else:
                        candidate_extra = get_candidate_extra(selected_candidate_id)

                        edit_candidate_name = st.text_input(
                            "Candidate Name",
                            value=candidate[1] or "",
                            key=f"edit_candidate_name_{selected_candidate_id}"
                        )

                        edit_candidate_email = st.text_input(
                            "Email",
                            value=candidate[8] or "",
                            key=f"edit_candidate_email_{selected_candidate_id}"
                        )

                        edit_candidate_phone = st.text_input(
                            "Phone",
                            value=candidate[9] or "",
                            key=f"edit_candidate_phone_{selected_candidate_id}"
                        )

                        edit_candidate_location = st.text_input(
                            "Candidate Location / Geo Location",
                            value=candidate[2] or "",
                            key=f"edit_candidate_location_{selected_candidate_id}"
                        )

                        current_role = candidate[3] if candidate[3] in APPLIED_ROLE_OPTIONS else ""
                        role_index = APPLIED_ROLE_OPTIONS.index(current_role)

                        edit_applied_role = st.selectbox(
                            "Applied Role",
                            APPLIED_ROLE_OPTIONS,
                            index=role_index,
                            key=f"edit_candidate_role_{selected_candidate_id}"
                        )

                        current_status = candidate[10] if candidate[10] in CANDIDATE_STATUS_OPTIONS else CANDIDATE_STATUS_OPTIONS[0]
                        status_index = CANDIDATE_STATUS_OPTIONS.index(current_status)

                        edit_candidate_status = st.selectbox(
                            "Candidate Category",
                            CANDIDATE_STATUS_OPTIONS,
                            index=status_index,
                            key=f"edit_candidate_status_{selected_candidate_id}"
                        )

                        edit_interview_date = st.text_input(
                            "Interview Date",
                            value=candidate_extra.get("interview_date", ""),
                            key=f"edit_candidate_interview_date_{selected_candidate_id}"
                        )

                        current_interviewer = candidate_extra.get("interviewer", "")

                        if current_interviewer in INTERVIEWER_OPTIONS:
                            interviewer_index = INTERVIEWER_OPTIONS.index(current_interviewer)
                        else:
                            interviewer_index = 0

                        edit_interviewer = st.selectbox(
                            "Interviewer",
                            INTERVIEWER_OPTIONS,
                            index=interviewer_index,
                            key=f"edit_candidate_interviewer_{selected_candidate_id}"
                        )

                        edit_resume_text = st.text_area(
                            "Resume Text",
                            value=candidate[4] or "",
                            height=220,
                            key=f"edit_candidate_resume_{selected_candidate_id}"
                        )

                        new_resume_file = st.file_uploader(
                            "Upload / Replace Resume",
                            type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
                            key=f"edit_candidate_resume_upload_{selected_candidate_id}"
                        )

                        if new_resume_file:
                            parsed_resume_text = parse_uploaded_resume_file(new_resume_file)

                            if parsed_resume_text:
                                edit_resume_text = parsed_resume_text
                                st.success("Resume uploaded and parsed. Click Save Candidate Changes to store it.")

                        edit_screening_answers = st.text_area(
                            "Screening Answers",
                            value=candidate[5] or "",
                            height=220,
                            key=f"edit_candidate_screening_{selected_candidate_id}"
                        )

                        map_best_client_on_save = st.checkbox(
                            "Map best client when saving",
                            value=False,
                            key=f"map_best_client_save_{selected_candidate_id}"
                        )

                        col_save, col_delete = st.columns(2)

                        with col_save:
                            if st.button("Save Candidate Changes", key=f"save_candidate_{selected_candidate_id}"):
                                if map_best_client_on_save:
                                    if role_uses_ai_need_matching(edit_applied_role) and not edit_resume_text.strip():
                                        new_client_id = candidate[11]
                                        new_client_name = candidate[12]
                                        new_value = candidate[13]
                                        st.warning("Resume is required for AI need-based client matching. Existing mapping was kept.")
                                    else:
                                        new_client_id, new_client_name, new_value = find_best_client_match_for_candidate_data(
                                            candidate_name=edit_candidate_name,
                                            candidate_location=edit_candidate_location,
                                            applied_role=edit_applied_role,
                                            resume_text=edit_resume_text,
                                            screening_answers=edit_screening_answers
                                        )
                                else:
                                    new_client_id = candidate[11]
                                    new_client_name = candidate[12]
                                    new_value = candidate[13]

                                update_candidate(
                                    candidate_id=selected_candidate_id,
                                    candidate_name=edit_candidate_name,
                                    email=edit_candidate_email,
                                    phone=edit_candidate_phone,
                                    location=edit_candidate_location,
                                    applied_role=edit_applied_role,
                                    resume_text=edit_resume_text,
                                    screening_answers=edit_screening_answers,
                                    portfolio_links=candidate[6],
                                    candidate_status=edit_candidate_status,
                                    matched_client_id=new_client_id,
                                    matched_client_name=new_client_name,
                                    matched_client_distance_miles=new_value
                                )

                                update_candidate_extra(
                                    selected_candidate_id,
                                    {
                                        "interview_date": edit_interview_date,
                                        "interviewer": edit_interviewer
                                    }
                                )

                                refreshed_candidate = get_candidate(selected_candidate_id)

                                if refreshed_candidate and candidate_has_resume(refreshed_candidate):
                                    parsed_resume_summary = create_resume_summary(refreshed_candidate)
                                    update_candidate_extra(
                                        selected_candidate_id,
                                        {"short_summary": parsed_resume_summary}
                                    )

                                st.success("Candidate updated.")
                                st.rerun()

                        with col_delete:
                            confirm_delete_candidate = st.checkbox(
                                "Confirm delete this candidate.",
                                key=f"confirm_delete_candidate_{selected_candidate_id}"
                            )

                            if st.button("Delete Candidate", key=f"delete_candidate_{selected_candidate_id}"):
                                if confirm_delete_candidate:
                                    delete_candidate(selected_candidate_id)

                                    if "selected_admin_candidate_id" in st.session_state:
                                        del st.session_state.selected_admin_candidate_id

                                    st.success("Candidate deleted.")
                                    st.rerun()
                                else:
                                    st.error("Please confirm before deleting.")

        with admin_tabs[5]:
            st.subheader("Admin Command Console")

            st.warning("Safe admin console only. It does not run server terminal commands.")

            st.code("""
show counts
show tables
list clients
list candidates
find client huntsville
find candidate john
delete client 1
delete candidate 1
""")

            admin_command = st.text_input("Enter admin command", key="admin_command")

            if st.button("Run Command", key="run_admin_command"):
                if not admin_command.strip():
                    st.error("Please enter a command.")
                else:
                    result = run_safe_admin_command(admin_command)

                    st.subheader("Command Result")
                    st.write(result)