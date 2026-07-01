import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from supabase_database import (
    search_candidates,
    get_candidate,
    search_clients,
    get_client,
    count_records
)

app = FastAPI(
    title="REPP Hiring Engine API",
    version="1.0.0"
)

API_KEY = os.getenv("REPP_API_KEY", "")


def check_api_key(x_api_key: str = Header(default="")):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="REPP_API_KEY is not configured on the server.")

    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def candidate_has_resume(candidate):
    resume_text = candidate[4] or ""

    if not resume_text.strip():
        return False

    if "no readable resume text could be extracted" in resume_text.lower():
        return False

    return True


def candidate_to_dict(candidate):
    return {
        "id": candidate[0],
        "candidate_name": candidate[1],
        "location": candidate[2],
        "applied_role": candidate[3],
        "resume_text": candidate[4],
        "screening_answers": candidate[5],
        "portfolio_links": candidate[6],
        "created_at": candidate[7],
        "email": candidate[8],
        "phone": candidate[9],
        "candidate_status": candidate[10],
        "matched_client_id": candidate[11],
        "matched_client_name": candidate[12],
        "matched_client_distance_miles": candidate[13],
        "has_resume": candidate_has_resume(candidate)
    }


def client_to_dict(client):
    return {
        "id": client[0],
        "client_name": client[1],
        "display_name": client[1],
        "role": client[2],
        "location": client[3],
        "client_needs": client[4],
        "formatted_client_needs": client[9]
    }


class CandidateSearchRequest(BaseModel):
    search_term: str = ""
    status_filter: str = ""
    role_filter: str = ""
    limit: int = 25
    offset: int = 0


class ClientSearchRequest(BaseModel):
    search_term: str = ""
    limit: int = 25


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "REPP Hiring Engine API"
    }


@app.get("/admin/counts")
def admin_counts(x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    return count_records()


@app.post("/candidates/search")
def api_search_candidates(request: CandidateSearchRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)

    candidates = search_candidates(
        search_term=request.search_term,
        status_filter=request.status_filter,
        role_filter=request.role_filter,
        limit=request.limit,
        offset=request.offset
    )

    return {
        "candidates": [candidate_to_dict(candidate) for candidate in candidates]
    }


@app.get("/candidates/{candidate_id}")
def api_get_candidate(candidate_id: int, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)

    candidate = get_candidate(candidate_id)

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    return candidate_to_dict(candidate)


@app.post("/clients/search")
def api_search_clients(request: ClientSearchRequest, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)

    clients = search_clients(
        search_term=request.search_term,
        limit=request.limit
    )

    return {
        "clients": [client_to_dict(client) for client in clients]
    }


@app.get("/clients/{client_id}")
def api_get_client(client_id: int, x_api_key: str = Header(default="")):
    check_api_key(x_api_key)

    client = get_client(client_id)

    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")

    return client_to_dict(client)