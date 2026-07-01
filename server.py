import os
import subprocess
import time
import asyncio
import httpx
import websockets

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from supabase_database import (
    search_candidates,
    get_candidate,
    search_clients,
    get_client,
    count_records
)


app = FastAPI(
    title="REPP Hiring Engine Gateway",
    version="1.0.0"
)

STREAMLIT_INTERNAL_PORT = int(os.getenv("STREAMLIT_INTERNAL_PORT", "8501"))
STREAMLIT_HOST = "127.0.0.1"
STREAMLIT_BASE_URL = f"http://{STREAMLIT_HOST}:{STREAMLIT_INTERNAL_PORT}"

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
        STREAMLIT_HOST,
        "--server.headless",
        "true",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false",
        "--server.baseUrlPath",
        "app"
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
    return RedirectResponse(url="/app/")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "REPP Hiring Engine",
        "web_app": "/app",
        "api": "/api"
    }


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


@app.api_route(
    "/app/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
)
async def proxy_streamlit_http(path: str, request: Request):
    target_url = f"{STREAMLIT_BASE_URL}/app/{path}"

    headers = dict(request.headers)
    headers.pop("host", None)

    body = await request.body()

    async with httpx.AsyncClient(timeout=None, follow_redirects=False) as client:
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )

    excluded_headers = {
        "content-encoding",
        "transfer-encoding",
        "connection"
        "content-length"
    }

    response_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in excluded_headers
    }

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type")
    )


@app.api_route(
    "/app",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
)
async def proxy_streamlit_root(request: Request):
    target_url = f"{STREAMLIT_BASE_URL}/app/"

    headers = dict(request.headers)
    headers.pop("host", None)

    body = await request.body()

    async with httpx.AsyncClient(timeout=None, follow_redirects=False) as client:
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )

    excluded_headers = {
        "content-encoding",
        "transfer-encoding",
        "connection"
    }

    response_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in excluded_headers
    }

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type")
    )


@app.websocket("/app/{path:path}")
async def proxy_streamlit_websocket(websocket: WebSocket, path: str):
    await websocket.accept()

    query_string = websocket.scope.get("query_string", b"").decode("utf-8")

    if query_string:
        target_ws_url = f"ws://{STREAMLIT_HOST}:{STREAMLIT_INTERNAL_PORT}/app/{path}?{query_string}"
    else:
        target_ws_url = f"ws://{STREAMLIT_HOST}:{STREAMLIT_INTERNAL_PORT}/app/{path}"

    try:
        async with websockets.connect(target_ws_url) as target_ws:

            async def client_to_streamlit():
                try:
                    while True:
                        message = await websocket.receive()

                        if "text" in message:
                            await target_ws.send(message["text"])

                        elif "bytes" in message:
                            await target_ws.send(message["bytes"])

                except Exception:
                    pass

            async def streamlit_to_client():
                try:
                    async for message in target_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)

                except Exception:
                    pass

            await asyncio.gather(
                client_to_streamlit(),
                streamlit_to_client()
            )

    except Exception:
        await websocket.close()
