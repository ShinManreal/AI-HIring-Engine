"""
Calendly integration for REPP Talent AI Hiring Engine.

Purpose:
- Check whether a candidate has already booked an interview in Calendly.
- Match by email, full name, first name + last name.
- Return date, time, interviewer, event name, and booking status.

Required Render / .env variable:
CALENDLY_API_KEY=your_calendly_personal_access_token

Optional variables:
CALENDLY_LOOKBACK_DAYS=30
CALENDLY_LOOKAHEAD_DAYS=120
CALENDLY_EVENT_LIMIT=100
"""

import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()

CALENDLY_API_BASE_URL = "https://api.calendly.com"

CALENDLY_API_KEY = (
    os.getenv("CALENDLY_API_KEY", "")
    or os.getenv("CALENDLY_ACCESS_TOKEN", "")
    or os.getenv("CALENDLY_TOKEN", "")
).strip()

CALENDLY_LOOKBACK_DAYS = int(os.getenv("CALENDLY_LOOKBACK_DAYS", "30"))
CALENDLY_LOOKAHEAD_DAYS = int(os.getenv("CALENDLY_LOOKAHEAD_DAYS", "120"))
CALENDLY_EVENT_LIMIT = int(os.getenv("CALENDLY_EVENT_LIMIT", "100"))

DISPLAY_TIMEZONE = os.getenv("CALENDLY_DISPLAY_TIMEZONE", "Asia/Manila")


def calendly_headers():
    return {
        "Authorization": f"Bearer {CALENDLY_API_KEY}",
        "Content-Type": "application/json",
    }


def normalize_text(value):
    return str(value or "").strip().lower()


def normalize_name(value):
    cleaned = normalize_text(value)
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def split_candidate_name(full_name):
    cleaned = normalize_name(full_name)

    if not cleaned:
        return "", ""

    parts = cleaned.split()

    if len(parts) == 1:
        return parts[0], ""

    return parts[0], parts[-1]


def names_match(candidate_name, invitee_name):
    candidate_clean = normalize_name(candidate_name)
    invitee_clean = normalize_name(invitee_name)

    if not candidate_clean or not invitee_clean:
        return False

    if candidate_clean == invitee_clean:
        return True

    first_name, last_name = split_candidate_name(candidate_clean)

    if first_name and last_name:
        return first_name in invitee_clean and last_name in invitee_clean

    return candidate_clean in invitee_clean or invitee_clean in candidate_clean


def emails_match(candidate_email, invitee_email):
    candidate_email = normalize_text(candidate_email)
    invitee_email = normalize_text(invitee_email)

    if not candidate_email or not invitee_email:
        return False

    return candidate_email == invitee_email


def calendly_get(path, params=None):
    if not CALENDLY_API_KEY:
        return {
            "ok": False,
            "status_code": 0,
            "error": "CALENDLY_API_KEY is missing.",
            "data": None,
        }

    url = f"{CALENDLY_API_BASE_URL}{path}"

    try:
        response = requests.get(
            url,
            headers=calendly_headers(),
            params=params or {},
            timeout=30,
        )

        if response.status_code >= 400:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": response.text,
                "data": None,
            }

        return {
            "ok": True,
            "status_code": response.status_code,
            "error": "",
            "data": response.json(),
        }

    except Exception as error:
        return {
            "ok": False,
            "status_code": 0,
            "error": str(error),
            "data": None,
        }


def get_current_user_and_org():
    response = calendly_get("/users/me")

    if not response["ok"]:
        return "", "", response["error"]

    data = response["data"].get("resource", {})
    user_uri = data.get("uri", "")
    organization_uri = data.get("current_organization", "")

    return user_uri, organization_uri, ""


def get_scheduled_events():
    user_uri, organization_uri, error = get_current_user_and_org()

    if error:
        return [], error

    now = datetime.now(timezone.utc)
    min_start_time = (now - timedelta(days=CALENDLY_LOOKBACK_DAYS)).isoformat().replace("+00:00", "Z")
    max_start_time = (now + timedelta(days=CALENDLY_LOOKAHEAD_DAYS)).isoformat().replace("+00:00", "Z")

    params = {
        "min_start_time": min_start_time,
        "max_start_time": max_start_time,
        "count": min(CALENDLY_EVENT_LIMIT, 100),
        "sort": "start_time:desc",
    }

    if organization_uri:
        params["organization"] = organization_uri
    elif user_uri:
        params["user"] = user_uri
    else:
        return [], "Calendly user/organization URI could not be determined."

    events = []
    next_page = None

    while True:
        page_params = dict(params)

        if next_page:
            # Calendly pagination returns a full next_page URL.
            try:
                page_response = requests.get(
                    next_page,
                    headers=calendly_headers(),
                    timeout=30,
                )

                if page_response.status_code >= 400:
                    return events, page_response.text

                data = page_response.json()
            except Exception as error:
                return events, str(error)
        else:
            response = calendly_get("/scheduled_events", page_params)

            if not response["ok"]:
                return events, response["error"]

            data = response["data"]

        events.extend(data.get("collection", []))

        pagination = data.get("pagination", {})
        next_page = pagination.get("next_page")

        if not next_page:
            break

        if len(events) >= CALENDLY_EVENT_LIMIT:
            break

    return events[:CALENDLY_EVENT_LIMIT], ""


def extract_uuid_from_uri(uri):
    if not uri:
        return ""

    return str(uri).rstrip("/").split("/")[-1]


def get_event_invitees(event):
    event_uri = event.get("uri", "")
    event_uuid = extract_uuid_from_uri(event_uri)

    if not event_uuid:
        return [], "Missing Calendly event UUID."

    invitees = []
    next_page = None

    while True:
        if next_page:
            try:
                response = requests.get(
                    next_page,
                    headers=calendly_headers(),
                    timeout=30,
                )

                if response.status_code >= 400:
                    return invitees, response.text

                data = response.json()
            except Exception as error:
                return invitees, str(error)
        else:
            response = calendly_get(
                f"/scheduled_events/{event_uuid}/invitees",
                params={"count": 100},
            )

            if not response["ok"]:
                return invitees, response["error"]

            data = response["data"]

        invitees.extend(data.get("collection", []))

        pagination = data.get("pagination", {})
        next_page = pagination.get("next_page")

        if not next_page:
            break

    return invitees, ""


def detect_interviewer(event, invitee=None):
    possible_names = ["Claire", "JR", "Shin", "Hernani"]

    searchable_parts = [
        event.get("name", ""),
        event.get("location", {}).get("location", "") if isinstance(event.get("location"), dict) else "",
    ]

    for membership in event.get("event_memberships", []) or []:
        searchable_parts.append(membership.get("user_name", ""))
        searchable_parts.append(membership.get("user_email", ""))

    if invitee:
        for question_answer in invitee.get("questions_and_answers", []) or []:
            searchable_parts.append(question_answer.get("question", ""))
            searchable_parts.append(question_answer.get("answer", ""))

    searchable_text = " ".join(str(part or "") for part in searchable_parts).lower()

    for name in possible_names:
        if name.lower() in searchable_text:
            return name

    # Calendly host fallback
    memberships = event.get("event_memberships", []) or []
    if memberships:
        host_name = memberships[0].get("user_name", "")
        if host_name:
            return host_name

    return "Not specified"


def format_calendly_datetime(start_time):
    if not start_time:
        return "Not specified", "Not specified"

    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        local_dt = start_dt.astimezone(ZoneInfo(DISPLAY_TIMEZONE))

        date_text = local_dt.strftime("%B %d, %Y")
        time_text = local_dt.strftime("%I:%M %p").lstrip("0")

        return date_text, time_text

    except Exception:
        return start_time, "Not specified"


def invitee_is_active(invitee):
    status = normalize_text(invitee.get("status", ""))

    if status in ["canceled", "cancelled"]:
        return False

    return True


def get_candidate_calendly_booking(candidate_name, candidate_email):
    """
    Returns:
    {
        "configured": bool,
        "booked": bool,
        "status": "Booked" / "Not Yet Booked" / "Calendly Not Configured" / "Calendly Error",
        "date": str,
        "time": str,
        "interviewer": str,
        "event_name": str,
        "invitee_name": str,
        "invitee_email": str,
        "error": str
    }
    """

    empty_result = {
        "configured": bool(CALENDLY_API_KEY),
        "booked": False,
        "status": "Not Yet Booked",
        "date": "",
        "time": "",
        "interviewer": "",
        "event_name": "",
        "invitee_name": "",
        "invitee_email": "",
        "error": "",
    }

    if not CALENDLY_API_KEY:
        empty_result["status"] = "Calendly Not Configured"
        empty_result["error"] = "CALENDLY_API_KEY is missing."
        return empty_result

    events, error = get_scheduled_events()

    if error:
        empty_result["status"] = "Calendly Error"
        empty_result["error"] = error
        return empty_result

    matched_booking = None

    for event in events:
        invitees, invitee_error = get_event_invitees(event)

        if invitee_error:
            continue

        for invitee in invitees:
            invitee_name = invitee.get("name", "")
            invitee_email = invitee.get("email", "")

            if not invitee_is_active(invitee):
                continue

            matched_by_email = emails_match(candidate_email, invitee_email)
            matched_by_name = names_match(candidate_name, invitee_name)

            if matched_by_email or matched_by_name:
                matched_booking = {
                    "event": event,
                    "invitee": invitee,
                    "matched_by": "email" if matched_by_email else "name",
                }
                break

        if matched_booking:
            break

    if not matched_booking:
        return empty_result

    event = matched_booking["event"]
    invitee = matched_booking["invitee"]
    date_text, time_text = format_calendly_datetime(event.get("start_time", ""))

    return {
        "configured": True,
        "booked": True,
        "status": "Booked",
        "date": date_text,
        "time": time_text,
        "interviewer": detect_interviewer(event, invitee),
        "event_name": event.get("name", "Calendly Interview"),
        "invitee_name": invitee.get("name", ""),
        "invitee_email": invitee.get("email", ""),
        "error": "",
    }
