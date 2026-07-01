import os
import subprocess
import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from supabase_database import (
    search_candidates,
    get_candidate,
    search_clients,
    get_client,
    count_records
)


# IMPORTANT:
# Render start command expects this exact variable:
# uvicorn server:app --host 0.0.0.0 --port $PORT

app = FastAPI(
    title="REPP Hiring Engine Gateway",
    version="1.0.0"
)


STREAMLIT_INTERNAL_PORT = int(os.getenv("STREAMLIT_INTERNAL_PORT", "8501"))
API_KEY = os.getenv("REPP_API_KEY", "")

streamlit_process = None


@app.on_event("startup")
def start_streamlit():
    global streamlit_process

    if streamlit_process is not None:
        return

    command = [
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        str(STREAMLIT_INTERNAL_PORT),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false"
    ]

    streamlit_process = subprocess.Popen(command)

    time.sleep(3)


@app.on_event("shutdown")
def stop_streamlit():
    global streamlit_process

    if streamlit_process is not None:
        streamlit_process.terminate()
        streamlit_process = None


def check_api_key(x_api_key: str = Header(default="")):
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="REPP_API_KEY is not configured on the server."
        )

    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key."
        )


def candidate_has_resume(candidate):
    resume_text = candidate[4] or ""

    if not resume_text.strip():
        return False

    if "no readable resume text could be extracted" in resume_text.lower():
        return False

    return True


def match_display_label(candidate):
    applied_role = candidate[3] or ""

    if applied_role in ["VA", "Editor", "Social Media Manager"]:
        return "Need Match Score"

    return "Distance"


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
        "match_display_label": match_display_label(candidate),
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


@app.get("/")
def root():
    return RedirectResponse(url="/app")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "REPP Hiring Engine",
        "web_app": "/app",
        "api": "/api"
    }


@app.get("/app")
def web_app_redirect():
    return RedirectResponse(url=f"http://localhost:{STREAMLIT_INTERNAL_PORT}")


@app.get("/api/admin/counts")
def admin_counts(x_api_key: str = Header(default="")):
    check_api_key(x_api_key)
    return count_records()


@app.post("/api/candidates/search")
def api_search_candidates(
    request: CandidateSearchRequest,
    x_api_key: str = Header(default="")
):
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


@app.get("/api/candidates/{candidate_id}")
def api_get_candidate(
    candidate_id: int,
    x_api_key: str = Header(default="")
):
    check_api_key(x_api_key)

    candidate = get_candidate(candidate_id)

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    return candidate_to_dict(candidate)


@app.post("/api/clients/search")
def api_search_clients(
    request: ClientSearchRequest,
    x_api_key: str = Header(default="")
):
    check_api_key(x_api_key)

    clients = search_clients(
        search_term=request.search_term,
        limit=request.limit
    )

    return {
        "clients": [client_to_dict(client) for client in clients]
    }


@app.get("/api/clients/{client_id}")
def api_get_client(
    client_id: int,
    x_api_key: str = Header(default="")
):
    check_api_key(x_api_key)

    client = get_client(client_id)

    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")

    return client_to_dict(client)
