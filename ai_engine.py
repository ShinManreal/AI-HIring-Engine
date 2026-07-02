import os
import requests
from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter").strip().lower()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

LIQUID_THINKING_MODEL = os.getenv(
    "LIQUID_THINKING_MODEL",
    "liquid/lfm-2.5-1.2b-thinking:free"
)

LIQUID_INSTRUCT_MODEL = os.getenv(
    "LIQUID_INSTRUCT_MODEL",
    "liquid/lfm-2.5-1.2b-instruct:free"
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """
You are REPP Talent's recruiting AI assistant.

You help screen candidates, summarize profiles, create interview scripts,
evaluate interview transcripts, and match candidates to client needs.

Rules:
- Be direct, practical, and recruiter-friendly.
- Use only the information provided.
- Do not invent candidate details, resume facts, client needs, or transcript details.
- Do not reference protected classes or sensitive personal traits.
- Focus only on job-relevant evidence.
- Prioritize client-specific requirements over general assumptions.
"""


def choose_liquid_model(prompt: str) -> str:
    prompt_lower = prompt.lower()

    thinking_keywords = [
        "evaluate",
        "evaluation",
        "transcript",
        "screen",
        "screening",
        "risk",
        "recommendation",
        "rank",
        "match",
        "mapping",
        "client fit",
        "client needs",
        "decision",
        "no-go",
        "proceed",
        "clarification"
    ]

    if any(keyword in prompt_lower for keyword in thinking_keywords):
        return LIQUID_THINKING_MODEL

    return LIQUID_INSTRUCT_MODEL


def generate_with_openrouter(prompt: str, model: str | None = None) -> str:
    if not OPENROUTER_API_KEY:
        return """
OpenRouter is selected, but OPENROUTER_API_KEY is missing.

How to fix:
Add this to your .env and Render environment variables:

AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
LIQUID_THINKING_MODEL=liquid/lfm-2.5-1.2b-thinking:free
LIQUID_INSTRUCT_MODEL=liquid/lfm-2.5-1.2b-instruct:free
"""

    selected_model = model or choose_liquid_model(prompt)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://repphiringengine.onrender.com",
        "X-Title": "REPP Talent AI Hiring Engine"
    }

    payload = {
        "model": selected_model,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            return f"""
OpenRouter request failed.

Model:
{selected_model}

Status code:
{response.status_code}

Response:
{response.text}
"""

        data = response.json()

        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

    except Exception as error:
        return f"""
OpenRouter AI engine is not available right now.

Selected model:
{selected_model}

Reason:
{str(error)}
"""


def generate_ai_response(prompt: str) -> str:
    if AI_PROVIDER == "openrouter":
        return generate_with_openrouter(prompt)

    return f"""
Unsupported AI_PROVIDER: {AI_PROVIDER}

Set this in .env and Render:

AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
"""
