
import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from supabase_database import supabase, count_records
from ai_engine import ask_ai
from prompts import screening_prompt, interview_script_prompt, evaluation_prompt

load_dotenv()

app = FastAPI(
    title="REPP Hiring Engine GPT Actions API",
    version="2.0.0",
    description="Supabase-backed candidate/client CRUD and AI actions for REPP Talent GPT."
)

API_KEY = os.getenv("REPP_API_KEY", "").strip()


def check_api_key(x_api_key: str = Header(default="")):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="REPP_API_KEY is not configured.")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def txt(value):
    return str(value or "").strip()


def ilike(value):
    return f"%{txt(value)}%"


def rows(response):
    return response.data or []


def candidate_row_to_dict(row):
    return {
        "id": row.get("id"),
        "candidate_name": row.get("candidate_name") or "",
        "location": row.get("location") or "",
        "applied_role": row.get("applied_role") or "",
        "resume_text": row.get("resume_text") or "",
        "screening_answers": row.get("screening_answers") or "",
        "portfolio_links": row.get("portfolio_links") or "",
        "created_at": row.get("created_at") or "",
        "email": row.get("email") or "",
        "phone": row.get("phone") or "",
        "candidate_status": row.get("candidate_status") or "",
        "matched_client_id": row.get("matched_client_id"),
        "matched_client_name": row.get("matched_client_name") or "",
        "matched_client_distance_miles": row.get("matched_client_distance_miles"),
        "workflow_stage": row.get("workflow_stage") or "",
        "screened_at": row.get("screened_at") or "",
        "interview_script_created_at": row.get("interview_script_created_at") or "",
        "interview_evaluated_at": row.get("interview_evaluated_at") or "",
        "evaluation_outcome": row.get("evaluation_outcome") or "",
        "calendly_booked": row.get("calendly_booked") or False,
        "calendly_interview_date": row.get("calendly_interview_date") or "",
        "calendly_interview_date_text": row.get("calendly_interview_date_text") or "",
        "calendly_interview_time_text": row.get("calendly_interview_time_text") or "",
        "calendly_interviewer": row.get("calendly_interviewer") or "",
        "calendly_status": row.get("calendly_status") or "",
    }


def client_row_to_dict(row):
    return {
        "id": row.get("id"),
        "client_name": row.get("client_name") or "",
        "role": row.get("role") or "",
        "location": row.get("location") or "",
        "client_needs": row.get("client_needs") or "",
        "formatted_client_needs": row.get("formatted_client_needs") or "",
    }


def get_candidate_dict(candidate_id: int):
    response = supabase.table("candidates").select("*").eq("id", candidate_id).limit(1).execute()
    data = rows(response)
    return candidate_row_to_dict(data[0]) if data else None


def get_client_dict(client_id: int):
    response = supabase.table("clients").select("*").eq("id", client_id).limit(1).execute()
    data = rows(response)
    return client_row_to_dict(data[0]) if data else None


def get_candidate_tuple(candidate_id: int):
    candidate = get_candidate_dict(candidate_id)
    if not candidate:
        return None
    return (
        candidate["id"],
        candidate["candidate_name"],
        candidate["location"],
        candidate["applied_role"],
        candidate["resume_text"],
        candidate["screening_answers"],
        candidate["portfolio_links"],
        candidate["created_at"],
        candidate["email"],
        candidate["phone"],
        candidate["candidate_status"],
        candidate["matched_client_id"],
        candidate["matched_client_name"],
        candidate["matched_client_distance_miles"],
    )


def get_client_tuple(client_id: int):
    client = get_client_dict(client_id)
    if not client:
        return None
    needs = client["formatted_client_needs"] or client["client_needs"]
    return (
        client["id"],
        client["client_name"],
        client["role"],
        client["location"],
        client["client_needs"],
        client["client_needs"],
        client["client_needs"],
        client["client_needs"],
        client["client_needs"],
        needs,
    )


def has_resume(candidate):
    resume_text = candidate.get("resume_text") or ""
    return bool(resume_text.strip()) and "no readable resume text could be extracted" not in resume_text.lower()


def save_candidate_extra(candidate_id: int, payload: dict):
    try:
        payload = dict(payload or {})
        payload["candidate_id"] = candidate_id
        supabase.table("candidate_extra").upsert(payload, on_conflict="candidate_id").execute()
    except Exception:
        pass


def insert_ai_record(table_name: str, payload: dict):
    try:
        supabase.table(table_name).insert(payload).execute()
    except Exception:
        pass


def resolve_candidate(identifier: str):
    identifier = txt(identifier)
    if not identifier:
        return None

    if identifier.isdigit():
        found = get_candidate_dict(int(identifier))
        if found:
            return found

    if "@" in identifier:
        response = supabase.table("candidates").select("*").ilike("email", identifier).limit(1).execute()
        data = rows(response)
        if data:
            return candidate_row_to_dict(data[0])

    response = (
        supabase.table("candidates")
        .select("*")
        .or_(f"candidate_name.ilike.{ilike(identifier)},email.ilike.{ilike(identifier)}")
        .limit(10)
        .execute()
    )
    data = rows(response)

    if data:
        return candidate_row_to_dict(data[0])

    parts = identifier.split()
    if len(parts) >= 2:
        first_name = parts[0].lower()
        last_name = parts[-1].lower()
        response = supabase.table("candidates").select("*").ilike("candidate_name", ilike(first_name)).limit(25).execute()
        for row in rows(response):
            if last_name in str(row.get("candidate_name") or "").lower():
                return candidate_row_to_dict(row)

    return None


def resolve_client(identifier: str):
    identifier = txt(identifier)
    if not identifier:
        return None

    if identifier.isdigit():
        found = get_client_dict(int(identifier))
        if found:
            return found

    response = (
        supabase.table("clients")
        .select("*")
        .or_(f"client_name.ilike.{ilike(identifier)},location.ilike.{ilike(identifier)},role.ilike.{ilike(identifier)}")
        .limit(10)
        .execute()
    )
    data = rows(response)
    return client_row_to_dict(data[0]) if data else None


def get_mapped_client(candidate, client_identifier=""):
    if candidate.get("matched_client_id"):
        client = get_client_dict(int(candidate["matched_client_id"]))
        if client:
            return client

    if client_identifier:
        client = resolve_client(client_identifier)
        if client:
            return client

    if candidate.get("matched_client_name"):
        client = resolve_client(candidate["matched_client_name"])
        if client:
            return client

    return None


class CandidateSearchRequest(BaseModel):
    query: str = ""
    status_filter: str = ""
    role_filter: str = ""
    limit: int = 25


class CandidateCreateRequest(BaseModel):
    candidate_name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    applied_role: str = ""
    resume_text: str = ""
    screening_answers: str = ""
    portfolio_links: str = ""
    candidate_status: str = "Prospects"
    matched_client_id: Optional[int] = None
    matched_client_name: str = ""


class CandidateUpdateRequest(BaseModel):
    identifier: str
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    applied_role: Optional[str] = None
    resume_text: Optional[str] = None
    screening_answers: Optional[str] = None
    portfolio_links: Optional[str] = None
    candidate_status: Optional[str] = None
    matched_client_id: Optional[int] = None
    matched_client_name: Optional[str] = None


class IdentifierRequest(BaseModel):
    identifier: str


class ClientSearchRequest(BaseModel):
    query: str = ""
    limit: int = 25


class ClientCreateRequest(BaseModel):
    client_name: str
    role: str = ""
    location: str = ""
    client_needs: str = ""
    formatted_client_needs: str = ""


class ClientUpdateRequest(BaseModel):
    identifier: str
    client_name: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    client_needs: Optional[str] = None
    formatted_client_needs: Optional[str] = None


class CandidateAIRequest(BaseModel):
    identifier: str
    client_identifier: str = ""


class EvaluationRequest(BaseModel):
    identifier: str
    transcript_text: str
    client_identifier: str = ""


@app.get("/")
def root():
    return {"status": "ok", "service": "REPP Hiring Engine GPT Actions API"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "REPP Hiring Engine GPT Actions API", "api": "/api"}


@app.get("/api/admin/counts")
def admin_counts(x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    return count_records()


@app.post("/api/candidates/search")
def search_candidates(request: CandidateSearchRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    q = supabase.table("candidates").select("*")

    if request.query:
        q = q.or_(
            f"candidate_name.ilike.{ilike(request.query)},"
            f"email.ilike.{ilike(request.query)},"
            f"phone.ilike.{ilike(request.query)},"
            f"location.ilike.{ilike(request.query)},"
            f"applied_role.ilike.{ilike(request.query)},"
            f"matched_client_name.ilike.{ilike(request.query)}"
        )

    if request.status_filter:
        q = q.eq("candidate_status", request.status_filter)

    if request.role_filter:
        q = q.eq("applied_role", request.role_filter)

    response = q.order("id", desc=True).limit(request.limit).execute()
    return {"candidates": [candidate_row_to_dict(row) for row in rows(response)]}


@app.get("/api/candidates/resolve")
def resolve_candidate_route(identifier: str, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    candidate = resolve_candidate(identifier)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return candidate


@app.post("/api/candidates")
def create_candidate(request: CandidateCreateRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    payload = request.model_dump()
    response = supabase.table("candidates").insert(payload).execute()
    data = rows(response)
    if not data:
        raise HTTPException(status_code=500, detail="Candidate was not created.")
    return {"status": "created", "candidate": candidate_row_to_dict(data[0])}


@app.patch("/api/candidates")
def update_candidate(request: CandidateUpdateRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    candidate = resolve_candidate(request.identifier)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    payload = {
        key: value for key, value in request.model_dump().items()
        if key != "identifier" and value is not None
    }

    if not payload:
        return {"status": "no_changes", "candidate": candidate}

    response = supabase.table("candidates").update(payload).eq("id", candidate["id"]).execute()
    data = rows(response)
    return {"status": "updated", "candidate": candidate_row_to_dict(data[0]) if data else get_candidate_dict(candidate["id"])}


@app.delete("/api/candidates")
def delete_candidate(request: IdentifierRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    candidate = resolve_candidate(request.identifier)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    supabase.table("candidates").delete().eq("id", candidate["id"]).execute()
    return {"status": "deleted", "deleted_candidate": candidate}


@app.post("/api/clients/search")
def search_clients(request: ClientSearchRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    q = supabase.table("clients").select("*")

    if request.query:
        q = q.or_(
            f"client_name.ilike.{ilike(request.query)},"
            f"location.ilike.{ilike(request.query)},"
            f"role.ilike.{ilike(request.query)},"
            f"client_needs.ilike.{ilike(request.query)},"
            f"formatted_client_needs.ilike.{ilike(request.query)}"
        )

    response = q.order("id", desc=True).limit(request.limit).execute()
    return {"clients": [client_row_to_dict(row) for row in rows(response)]}


@app.get("/api/clients/resolve")
def resolve_client_route(identifier: str, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    client = resolve_client(identifier)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


@app.post("/api/clients")
def create_client(request: ClientCreateRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    payload = request.model_dump()
    payload["formatted_client_needs"] = payload.get("formatted_client_needs") or payload.get("client_needs")
    response = supabase.table("clients").insert(payload).execute()
    data = rows(response)
    if not data:
        raise HTTPException(status_code=500, detail="Client was not created.")
    return {"status": "created", "client": client_row_to_dict(data[0])}


@app.patch("/api/clients")
def update_client(request: ClientUpdateRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    client = resolve_client(request.identifier)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    payload = {
        key: value for key, value in request.model_dump().items()
        if key != "identifier" and value is not None
    }
    if not payload:
        return {"status": "no_changes", "client": client}
    response = supabase.table("clients").update(payload).eq("id", client["id"]).execute()
    data = rows(response)
    return {"status": "updated", "client": client_row_to_dict(data[0]) if data else get_client_dict(client["id"])}


@app.delete("/api/clients")
def delete_client(request: IdentifierRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    client = resolve_client(request.identifier)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    supabase.table("clients").delete().eq("id", client["id"]).execute()
    return {"status": "deleted", "deleted_client": client}


@app.post("/api/ai/screen-candidate")
def screen_candidate(request: CandidateAIRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    candidate = resolve_candidate(request.identifier)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if not has_resume(candidate):
        raise HTTPException(status_code=400, detail="Candidate has no readable resume text.")

    client = get_mapped_client(candidate, request.client_identifier)
    if not client:
        raise HTTPException(status_code=400, detail="No mapped client found.")

    result = ask_ai(screening_prompt(get_candidate_tuple(candidate["id"]), get_client_tuple(client["id"])))
    insert_ai_record("screening_results", {"candidate_id": candidate["id"], "client_id": client["id"], "screening_result": result})
    save_candidate_extra(candidate["id"], {"latest_screening_result": result})
    return {"status": "screened", "candidate": candidate, "client": client, "screening_result": result}


@app.post("/api/ai/create-interview-script")
def create_interview_script(request: CandidateAIRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    candidate = resolve_candidate(request.identifier)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if not has_resume(candidate):
        raise HTTPException(status_code=400, detail="Candidate has no readable resume text.")

    client = get_mapped_client(candidate, request.client_identifier)
    if not client:
        raise HTTPException(status_code=400, detail="No mapped client found.")

    result = ask_ai(interview_script_prompt(get_candidate_tuple(candidate["id"]), get_client_tuple(client["id"])))
    insert_ai_record("interview_scripts", {"candidate_id": candidate["id"], "client_id": client["id"], "script": result})
    save_candidate_extra(candidate["id"], {"latest_interview_script": result})
    return {"status": "script_created", "candidate": candidate, "client": client, "interview_script": result}


@app.post("/api/ai/evaluate-interview")
def evaluate_interview(request: EvaluationRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    candidate = resolve_candidate(request.identifier)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if not request.transcript_text.strip():
        raise HTTPException(status_code=400, detail="Transcript text is required.")

    client = get_mapped_client(candidate, request.client_identifier)
    if not client:
        raise HTTPException(status_code=400, detail="No mapped client found.")

    result = ask_ai(evaluation_prompt(get_candidate_tuple(candidate["id"]), get_client_tuple(client["id"]), request.transcript_text))
    insert_ai_record("evaluations", {"candidate_id": candidate["id"], "client_id": client["id"], "transcript_text": request.transcript_text, "evaluation": result})
    save_candidate_extra(candidate["id"], {"latest_evaluation": result})
    return {"status": "evaluated", "candidate": candidate, "client": client, "evaluation": result}


# ============================================================

class MassScreenCandidateItem(BaseModel):
    candidate_name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    applied_role: str = ""
    resume_text: str
    screening_answers: str = ""
    client_identifier: str = ""


class MassScreenRequest(BaseModel):
    candidates: list[MassScreenCandidateItem]
    default_client_identifier: str = ""
    add_to_database: bool = False
    default_candidate_status: str = "Prospects"


class CandidateCSVImportItem(BaseModel):
    candidate_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    applied_role: str = ""
    resume_text: str = ""
    screening_answers: str = ""
    portfolio_links: str = ""
    candidate_status: str = "Prospects"
    matched_client_id: Optional[int] = None
    matched_client_name: str = ""


class CandidateCSVImportRequest(BaseModel):
    candidates: list[CandidateCSVImportItem]
    default_candidate_status: str = "Prospects"


class ClientCSVImportItem(BaseModel):
    client_name: str
    location: str
    role: str
    client_needs: str = ""
    formatted_client_needs: str = ""


class ClientCSVImportRequest(BaseModel):
    clients: list[ClientCSVImportItem]

# MASS SCREENING
# ============================================================

def build_mass_screen_prompt(candidate_item: MassScreenCandidateItem, client: dict | None):
    client_text = "No mapped client provided."

    if client:
        client_text = f"""
Client Name:
{client.get("client_name") or ""}

Role:
{client.get("role") or ""}

Location:
{client.get("location") or ""}

Client Needs:
{client.get("formatted_client_needs") or client.get("client_needs") or ""}
"""

    return f"""
You are REPP Talent's pre-screening evaluator.

Task:
Screen this candidate for whether REPP should invest an initial interview slot.

Return ONLY this exact format:

Name: [Candidate Name]
Interview Decision: [Proceed to Initial Interview / Needs Clarification / No-Go Pre-Interview]
Reason: [1-2 concise sentences tied to the client needs, resume evidence, and any risk.]

Rules:
- Do not summarize the full resume.
- Do not overpraise.
- Do not invent facts.
- Check for competing business risk.
- Check for real estate license conflict.
- If the candidate is generally viable and remaining issues can be verified in interview, choose Proceed to Initial Interview.
- If critical information is missing, choose Needs Clarification.
- If a confirmed disqualifier or serious client mismatch exists, choose No-Go Pre-Interview.

Candidate Name:
{candidate_item.candidate_name}

Email:
{candidate_item.email}

Location:
{candidate_item.location}

Applied Role:
{candidate_item.applied_role}

Resume Text:
{candidate_item.resume_text}

Screening Answers:
{candidate_item.screening_answers}

Client:
{client_text}
"""


def create_candidate_from_mass_screen_item(
    candidate_item: MassScreenCandidateItem,
    client: dict | None,
    status: str
):
    payload = {
        "candidate_name": candidate_item.candidate_name,
        "email": candidate_item.email,
        "phone": candidate_item.phone,
        "location": candidate_item.location,
        "applied_role": candidate_item.applied_role,
        "resume_text": candidate_item.resume_text,
        "screening_answers": candidate_item.screening_answers,
        "portfolio_links": "",
        "candidate_status": status,
        "matched_client_id": client.get("id") if client else None,
        "matched_client_name": client.get("client_name") if client else "",
    }

    try:
        response = supabase.table("candidates").insert(payload).execute()
        data = rows(response)
        return candidate_row_to_dict(data[0]) if data else None
    except Exception:
        return None


@app.post("/api/ai/mass-screen-candidates")
def mass_screen_candidates(
    request: MassScreenRequest,
    x_api_key: str = Header(default="")
):
    check_api_key(x_api_key)

    if not request.candidates:
        raise HTTPException(status_code=400, detail="No candidates provided.")

    if len(request.candidates) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 candidates per mass screening batch.")

    results = []

    for candidate_item in request.candidates:
        if not candidate_item.resume_text.strip():
            results.append({
                "name": candidate_item.candidate_name,
                "interview_decision": "Needs Clarification",
                "reason": "No readable resume text was provided, so REPP cannot make a confident pre-screening decision.",
                "saved_candidate": None
            })
            continue

        client_identifier = candidate_item.client_identifier or request.default_client_identifier
        client = resolve_client(client_identifier) if client_identifier else None

        prompt = build_mass_screen_prompt(candidate_item, client)
        ai_result = ask_ai(prompt)

        saved_candidate = None
        if request.add_to_database:
            saved_candidate = create_candidate_from_mass_screen_item(
                candidate_item,
                client,
                request.default_candidate_status
            )

        results.append({
            "name": candidate_item.candidate_name,
            "screening_output": ai_result,
            "saved_candidate": saved_candidate
        })

    return {
        "status": "mass_screened",
        "count": len(results),
        "results": results
    }


# ============================================================
# CSV IMPORT WITH DUPLICATE SKIP
# ============================================================

def normalize_for_duplicate(value):
    return str(value or "").strip().lower()


def get_candidate_duplicate_matches(candidate_name="", email=""):
    matches = []
    seen_ids = set()

    candidate_name = str(candidate_name or "").strip()
    email = str(email or "").strip()

    if email:
        response = (
            supabase.table("candidates")
            .select("*")
            .ilike("email", email)
            .limit(10)
            .execute()
        )

        for row in rows(response):
            candidate = candidate_row_to_dict(row)
            if candidate["id"] not in seen_ids:
                candidate["duplicate_match_reason"] = "Email match"
                matches.append(candidate)
                seen_ids.add(candidate["id"])

    if candidate_name:
        response = (
            supabase.table("candidates")
            .select("*")
            .ilike("candidate_name", candidate_name)
            .limit(10)
            .execute()
        )

        for row in rows(response):
            candidate = candidate_row_to_dict(row)
            if candidate["id"] not in seen_ids:
                candidate["duplicate_match_reason"] = "Exact name match"
                matches.append(candidate)
                seen_ids.add(candidate["id"])

        parts = candidate_name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = parts[-1]

            response = (
                supabase.table("candidates")
                .select("*")
                .ilike("candidate_name", f"%{first_name}%")
                .limit(25)
                .execute()
            )

            for row in rows(response):
                row_name = normalize_for_duplicate(row.get("candidate_name"))

                if last_name.lower() in row_name:
                    candidate = candidate_row_to_dict(row)
                    if candidate["id"] not in seen_ids:
                        candidate["duplicate_match_reason"] = "First + last name match"
                        matches.append(candidate)
                        seen_ids.add(candidate["id"])

    return matches


def get_client_duplicate_match(client_name="", location="", role=""):
    client_name = str(client_name or "").strip()
    location = str(location or "").strip()
    role = str(role or "").strip()

    if not client_name or not location or not role:
        return None

    response = (
        supabase.table("clients")
        .select("*")
        .ilike("client_name", client_name)
        .ilike("location", location)
        .ilike("role", role)
        .limit(1)
        .execute()
    )

    data = rows(response)

    if not data:
        return None

    return client_row_to_dict(data[0])


def candidate_duplicate_display(candidate):
    return {
        "Name": candidate.get("candidate_name") or "",
        "Client": candidate.get("matched_client_name") or "",
        "Location": candidate.get("location") or "",
        "Status": candidate.get("candidate_status") or "",
        "Workflow Stage": candidate.get("workflow_stage") or "",
        "Interview Date": candidate.get("calendly_interview_date_text") or candidate.get("calendly_interview_date") or "",
        "Interviewer": candidate.get("calendly_interviewer") or "",
        "Evaluation Outcome": candidate.get("evaluation_outcome") or "",
    }


@app.post("/api/candidates/import-csv")
def import_candidates_csv(
    request: CandidateCSVImportRequest,
    x_api_key: str = Header(default="")
):
    check_api_key(x_api_key)

    created = []
    skipped_duplicates = []
    skipped_invalid = []

    for item in request.candidates:
        candidate_name = str(item.candidate_name or "").strip()
        email = str(item.email or "").strip()

        if not candidate_name and not email:
            skipped_invalid.append({
                "reason": "Missing candidate_name and email.",
                "row": item.model_dump()
            })
            continue

        duplicate_matches = get_candidate_duplicate_matches(candidate_name, email)

        if duplicate_matches:
            skipped_duplicates.append({
                "row": item.model_dump(),
                "duplicate_details": [
                    {
                        "match_reason": candidate.get("duplicate_match_reason", ""),
                        "details": candidate_duplicate_display(candidate),
                    }
                    for candidate in duplicate_matches
                ]
            })
            continue

        payload = item.model_dump()
        payload["candidate_status"] = payload.get("candidate_status") or request.default_candidate_status
        payload["workflow_stage"] = "New"

        try:
            response = supabase.table("candidates").insert(payload).execute()
            data = rows(response)

            if data:
                created.append(candidate_row_to_dict(data[0]))
            else:
                skipped_invalid.append({
                    "reason": "Supabase insert returned no row.",
                    "row": item.model_dump()
                })

        except Exception as error:
            skipped_invalid.append({
                "reason": str(error),
                "row": item.model_dump()
            })

    return {
        "status": "csv_import_completed",
        "created_count": len(created),
        "skipped_duplicate_count": len(skipped_duplicates),
        "skipped_invalid_count": len(skipped_invalid),
        "created": created,
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid,
        "rule": "Duplicates are not saved. Only candidates not already known in Supabase are inserted."
    }


@app.post("/api/clients/import-csv")
def import_clients_csv(
    request: ClientCSVImportRequest,
    x_api_key: str = Header(default="")
):
    check_api_key(x_api_key)

    created = []
    skipped_duplicates = []
    skipped_invalid = []

    for item in request.clients:
        client_name = str(item.client_name or "").strip()
        location = str(item.location or "").strip()
        role = str(item.role or "").strip()

        if not client_name or not location or not role:
            skipped_invalid.append({
                "reason": "client_name, location, and role are all required for duplicate-safe client import.",
                "row": item.model_dump()
            })
            continue

        duplicate = get_client_duplicate_match(client_name, location, role)

        if duplicate:
            skipped_duplicates.append({
                "row": item.model_dump(),
                "duplicate_client": duplicate,
                "match_rule": "Duplicate only when client_name + location + role all match."
            })
            continue

        payload = item.model_dump()
        payload["formatted_client_needs"] = payload.get("formatted_client_needs") or payload.get("client_needs")

        try:
            response = supabase.table("clients").insert(payload).execute()
            data = rows(response)

            if data:
                created.append(client_row_to_dict(data[0]))
            else:
                skipped_invalid.append({
                    "reason": "Supabase insert returned no row.",
                    "row": item.model_dump()
                })

        except Exception as error:
            skipped_invalid.append({
                "reason": str(error),
                "row": item.model_dump()
            })

    return {
        "status": "csv_import_completed",
        "created_count": len(created),
        "skipped_duplicate_count": len(skipped_duplicates),
        "skipped_invalid_count": len(skipped_invalid),
        "created": created,
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid,
        "rule": "Client duplicates are skipped only when client_name + location + role all match. Same client with different role is allowed."
    }


# ============================================================
# CALENDLY SYNC FOR GPT ACTIONS
# ============================================================

import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


CALENDLY_API_KEY = os.getenv("CALENDLY_API_KEY", "").strip()
CALENDLY_BASE_URL = "https://api.calendly.com"
CALENDLY_DISPLAY_TIMEZONE = os.getenv("CALENDLY_DISPLAY_TIMEZONE", "Asia/Manila").strip()
CALENDLY_LOOKBACK_DAYS = int(os.getenv("CALENDLY_LOOKBACK_DAYS", "90"))
CALENDLY_LOOKAHEAD_DAYS = int(os.getenv("CALENDLY_LOOKAHEAD_DAYS", "120"))
CALENDLY_EVENT_LIMIT = int(os.getenv("CALENDLY_EVENT_LIMIT", "100"))


class CalendlyCandidateRequest(BaseModel):
    identifier: str
    update_supabase: bool = True


class CalendlyRecentSyncRequest(BaseModel):
    update_supabase: bool = True
    lookback_days: int = CALENDLY_LOOKBACK_DAYS
    lookahead_days: int = CALENDLY_LOOKAHEAD_DAYS
    max_events: int = CALENDLY_EVENT_LIMIT


def calendly_headers():
    if not CALENDLY_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="CALENDLY_API_KEY is not configured on the API service."
        )

    return {
        "Authorization": f"Bearer {CALENDLY_API_KEY}",
        "Content-Type": "application/json",
    }


def calendly_get(path, params=None):
    response = requests.get(
        f"{CALENDLY_BASE_URL}{path}",
        headers=calendly_headers(),
        params=params or {},
        timeout=60,
    )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Calendly API error: {response.text}"
        )

    return response.json()


def get_calendly_user_context():
    data = calendly_get("/users/me")
    resource = data.get("resource") or {}

    return {
        "user_uri": resource.get("uri") or "",
        "organization_uri": resource.get("current_organization") or "",
        "name": resource.get("name") or "",
        "email": resource.get("email") or "",
    }


def parse_calendly_uuid(uri):
    return str(uri or "").rstrip("/").split("/")[-1]


def list_calendly_events(lookback_days=None, lookahead_days=None, max_events=None):
    context = get_calendly_user_context()

    lookback_days = lookback_days if lookback_days is not None else CALENDLY_LOOKBACK_DAYS
    lookahead_days = lookahead_days if lookahead_days is not None else CALENDLY_LOOKAHEAD_DAYS
    max_events = max_events if max_events is not None else CALENDLY_EVENT_LIMIT

    now = datetime.now(timezone.utc)
    min_start_time = (now - timedelta(days=lookback_days)).isoformat().replace("+00:00", "Z")
    max_start_time = (now + timedelta(days=lookahead_days)).isoformat().replace("+00:00", "Z")

    params = {
        "min_start_time": min_start_time,
        "max_start_time": max_start_time,
        "sort": "start_time:desc",
        "count": min(max_events, 100),
    }

    if context["organization_uri"]:
        params["organization"] = context["organization_uri"]
    else:
        params["user"] = context["user_uri"]

    data = calendly_get("/scheduled_events", params=params)
    return data.get("collection") or []


def list_event_invitees(event_uri):
    event_uuid = parse_calendly_uuid(event_uri)

    if not event_uuid:
        return []

    data = calendly_get(
        f"/scheduled_events/{event_uuid}/invitees",
        params={"count": 100},
    )

    return data.get("collection") or []


def normalize_match_text(value):
    return str(value or "").strip().lower()


def names_look_related(candidate_name, invitee_name):
    candidate_name = normalize_match_text(candidate_name)
    invitee_name = normalize_match_text(invitee_name)

    if not candidate_name or not invitee_name:
        return False

    if candidate_name == invitee_name:
        return True

    if candidate_name in invitee_name or invitee_name in candidate_name:
        return True

    candidate_parts = [part for part in candidate_name.split() if len(part) > 1]
    invitee_parts = [part for part in invitee_name.split() if len(part) > 1]

    if len(candidate_parts) >= 2:
        first_name = candidate_parts[0]
        last_name = candidate_parts[-1]
        return first_name in invitee_parts and last_name in invitee_parts

    return False


def event_interviewer_name(event):
    memberships = event.get("event_memberships") or []

    for membership in memberships:
        user_name = membership.get("user_name") or ""
        if user_name:
            return user_name

    event_name = event.get("name") or ""
    known_names = ["Claire", "JR", "Shin", "Hernani", "Nani", "Leesa", "Anny"]

    for name in known_names:
        if name.lower() in event_name.lower():
            return name

    return "Not specified"


def format_calendly_start(start_time):
    if not start_time:
        return "", ""

    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        local_dt = start_dt.astimezone(ZoneInfo(CALENDLY_DISPLAY_TIMEZONE))
        return local_dt.strftime("%B %d, %Y"), local_dt.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return start_time, ""


def find_candidate_calendly_booking(candidate):
    candidate_name = candidate.get("candidate_name") or ""
    candidate_email = normalize_match_text(candidate.get("email"))

    events = list_calendly_events()

    for event in events:
        event_uri = event.get("uri") or ""
        invitees = list_event_invitees(event_uri)

        for invitee in invitees:
            if invitee.get("canceled"):
                continue

            invitee_email = normalize_match_text(invitee.get("email"))
            invitee_name = invitee.get("name") or ""

            email_matches = bool(candidate_email and invitee_email and candidate_email == invitee_email)
            name_matches = names_look_related(candidate_name, invitee_name)

            if not email_matches and not name_matches:
                continue

            date_text, time_text = format_calendly_start(event.get("start_time") or "")

            return {
                "booked": True,
                "status": "Booked",
                "event_uri": event_uri,
                "event_name": event.get("name") or "",
                "invitee_uri": invitee.get("uri") or "",
                "invitee_name": invitee_name,
                "invitee_email": invitee.get("email") or "",
                "interview_date": event.get("start_time") or "",
                "interview_date_text": date_text,
                "interview_time_text": time_text,
                "interviewer": event_interviewer_name(event),
            }

    return {
        "booked": False,
        "status": "Not Yet Booked",
        "event_uri": "",
        "event_name": "",
        "invitee_uri": "",
        "invitee_name": "",
        "invitee_email": "",
        "interview_date": "",
        "interview_date_text": "",
        "interview_time_text": "",
        "interviewer": "",
    }


def update_candidate_calendly_columns(candidate_id, booking):
    payload = {
        "calendly_booked": bool(booking.get("booked")),
        "calendly_event_uri": booking.get("event_uri") or "",
        "calendly_event_name": booking.get("event_name") or "",
        "calendly_invitee_uri": booking.get("invitee_uri") or "",
        "calendly_invitee_name": booking.get("invitee_name") or "",
        "calendly_invitee_email": booking.get("invitee_email") or "",
        "calendly_interview_date": booking.get("interview_date") or None,
        "calendly_interview_date_text": booking.get("interview_date_text") or "",
        "calendly_interview_time_text": booking.get("interview_time_text") or "",
        "calendly_interviewer": booking.get("interviewer") or "",
        "calendly_status": booking.get("status") or "",
        "calendly_last_checked_at": datetime.now(timezone.utc).isoformat(),
    }

    current_candidate = get_candidate_dict(candidate_id) or {}
    current_stage = current_candidate.get("workflow_stage") or ""

    if booking.get("booked") and current_stage != "Interview Done":
        payload["workflow_stage"] = "Interviewing"

    response = (
        supabase.table("candidates")
        .update(payload)
        .eq("id", candidate_id)
        .execute()
    )

    data = rows(response)
    return candidate_row_to_dict(data[0]) if data else get_candidate_dict(candidate_id)


def calendly_duplicate_summary(candidate, booking=None):
    booking = booking or {}

    return {
        "Name": candidate.get("candidate_name") or "",
        "Client": candidate.get("matched_client_name") or "",
        "Location": candidate.get("location") or "",
        "Status": candidate.get("candidate_status") or "",
        "Workflow Stage": candidate.get("workflow_stage") or "",
        "Interview Date": (
            booking.get("interview_date_text")
            or candidate.get("calendly_interview_date_text")
            or candidate.get("calendly_interview_date")
            or ""
        ),
        "Interview Time": (
            booking.get("interview_time_text")
            or candidate.get("calendly_interview_time_text")
            or ""
        ),
        "Interviewer": (
            booking.get("interviewer")
            or candidate.get("calendly_interviewer")
            or ""
        ),
        "Evaluation Outcome": candidate.get("evaluation_outcome") or "",
    }


@app.post("/api/calendly/check-candidate-booking")
def check_candidate_calendly_booking(
    request: CalendlyCandidateRequest,
    x_api_key: str = Header(default="")
):
    check_api_key(x_api_key)

    candidate = resolve_candidate(request.identifier)

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    booking = find_candidate_calendly_booking(candidate)
    updated_candidate = None

    if request.update_supabase:
        updated_candidate = update_candidate_calendly_columns(candidate["id"], booking)

    return {
        "status": "checked",
        "candidate": updated_candidate or candidate,
        "booking": booking,
        "duplicate_display": calendly_duplicate_summary(updated_candidate or candidate, booking),
    }


@app.post("/api/calendly/sync-candidate-booking")
def sync_candidate_calendly_booking(
    request: CalendlyCandidateRequest,
    x_api_key: str = Header(default="")
):
    check_api_key(x_api_key)

    candidate = resolve_candidate(request.identifier)

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    booking = find_candidate_calendly_booking(candidate)
    updated_candidate = update_candidate_calendly_columns(candidate["id"], booking)

    return {
        "status": "synced",
        "candidate": updated_candidate,
        "booking": booking,
        "duplicate_display": calendly_duplicate_summary(updated_candidate, booking),
    }


@app.post("/api/calendly/sync-recent-bookings")
def sync_recent_calendly_bookings(
    request: CalendlyRecentSyncRequest,
    x_api_key: str = Header(default="")
):
    check_api_key(x_api_key)

    events = list_calendly_events(
        lookback_days=request.lookback_days,
        lookahead_days=request.lookahead_days,
        max_events=request.max_events,
    )

    synced = []
    unmatched = []

    for event in events:
        invitees = list_event_invitees(event.get("uri") or "")

        for invitee in invitees:
            if invitee.get("canceled"):
                continue

            invitee_email = invitee.get("email") or ""
            invitee_name = invitee.get("name") or ""

            candidate = resolve_candidate(invitee_email) if invitee_email else None

            if not candidate and invitee_name:
                candidate = resolve_candidate(invitee_name)

            date_text, time_text = format_calendly_start(event.get("start_time") or "")

            booking = {
                "booked": True,
                "status": "Booked",
                "event_uri": event.get("uri") or "",
                "event_name": event.get("name") or "",
                "invitee_uri": invitee.get("uri") or "",
                "invitee_name": invitee_name,
                "invitee_email": invitee_email,
                "interview_date": event.get("start_time") or "",
                "interview_date_text": date_text,
                "interview_time_text": time_text,
                "interviewer": event_interviewer_name(event),
            }

            if candidate:
                updated_candidate = (
                    update_candidate_calendly_columns(candidate["id"], booking)
                    if request.update_supabase
                    else candidate
                )

                synced.append({
                    "candidate": updated_candidate,
                    "booking": booking,
                    "duplicate_display": calendly_duplicate_summary(updated_candidate, booking),
                })
            else:
                unmatched.append({
                    "invitee_name": invitee_name,
                    "invitee_email": invitee_email,
                    "event_name": event.get("name") or "",
                    "interview_date": date_text,
                    "interview_time": time_text,
                    "interviewer": event_interviewer_name(event),
                })

    return {
        "status": "recent_bookings_synced",
        "synced_count": len(synced),
        "unmatched_count": len(unmatched),
        "synced": synced,
        "unmatched": unmatched,
    }
