"""
REPP Talent AI Engine - OpenRouter Multi-Model Fallback Chain

Primary:
- LiquidAI models

Fallback:
- Configurable OpenRouter fallback models
- Uses verified OpenRouter-style model IDs where possible

IMPORTANT:
Do not put plain display names like "glm-5.2" unless OpenRouter accepts that exact ID.
Use provider/model IDs like:
- z-ai/glm-5.2
- moonshotai/kimi-k2.7-code
- nvidia/nemotron-3-ultra-550b-a55b:free
- qwen/qwen3.5-35b-a3b

Required Render variables:
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here

Primary:
LIQUID_THINKING_MODEL=liquid/lfm-2.5-1.2b-thinking:free
LIQUID_INSTRUCT_MODEL=liquid/lfm-2.5-1.2b-instruct:free

Recommended fallback chain:
OPENROUTER_BACKUP_MODELS=z-ai/glm-5.2,moonshotai/kimi-k2.7-code,nvidia/nemotron-3-ultra-550b-a55b:free,qwen/qwen3.5-35b-a3b,meta-llama/llama-3.3-70b-instruct:free,meta-llama/llama-3.2-3b-instruct:free,openrouter/free

Optional:
OPENROUTER_SITE_URL=https://repphiringengine.onrender.com
OPENROUTER_SITE_NAME=REPP Talent AI Hiring Engine
OPENROUTER_TIMEOUT_SECONDS=120
AI_MAX_TOKENS=4000
AI_TEMPERATURE=0.2
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter").strip().lower()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

OPENROUTER_SITE_URL = os.getenv(
    "OPENROUTER_SITE_URL",
    "https://repphiringengine.onrender.com"
).strip()

OPENROUTER_SITE_NAME = os.getenv(
    "OPENROUTER_SITE_NAME",
    "REPP Talent AI Hiring Engine"
).strip()

LIQUID_THINKING_MODEL = os.getenv(
    "LIQUID_THINKING_MODEL",
    "liquid/lfm-2.5-1.2b-thinking:free"
).strip()

LIQUID_INSTRUCT_MODEL = os.getenv(
    "LIQUID_INSTRUCT_MODEL",
    "liquid/lfm-2.5-1.2b-instruct:free"
).strip()

DEFAULT_BACKUP_MODELS = (
    "z-ai/glm-5.2,"
    "moonshotai/kimi-k2.7-code,"
    "nvidia/nemotron-3-ultra-550b-a55b:free,"
    "qwen/qwen3.5-35b-a3b,"
    "meta-llama/llama-3.3-70b-instruct:free,"
    "meta-llama/llama-3.2-3b-instruct:free,"
    "openrouter/free"
)

OPENROUTER_BACKUP_MODELS = os.getenv(
    "OPENROUTER_BACKUP_MODELS",
    DEFAULT_BACKUP_MODELS
).strip()

# Backward compatibility with older variable names.
LLAMA_BACKUP_MODELS = os.getenv("LLAMA_BACKUP_MODELS", "").strip()
LLAMA_BACKUP_MODEL = os.getenv("LLAMA_BACKUP_MODEL", "").strip()

OPENROUTER_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "120"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "4000"))
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.2"))

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
- Prioritize client-specific requirements over general hiring assumptions.
"""


def choose_liquid_model(prompt: str) -> str:
    prompt_lower = str(prompt or "").lower()

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
        "clarification",
        "compare",
        "score",
        "finalist",
        "red flag",
        "disqualifier",
        "star rating",
        "fbi profiler",
    ]

    if any(keyword in prompt_lower for keyword in thinking_keywords):
        return LIQUID_THINKING_MODEL

    return LIQUID_INSTRUCT_MODEL


def parse_model_list(raw_value: str) -> list[str]:
    models = []

    for item in str(raw_value or "").split(","):
        model = item.strip()

        if model and model not in models:
            models.append(model)

    return models


def build_model_attempts(primary_model: str) -> list[str]:
    attempts = []

    if primary_model:
        attempts.append(primary_model)

    raw_fallback_lists = [
        OPENROUTER_BACKUP_MODELS,
        LLAMA_BACKUP_MODELS,
        LLAMA_BACKUP_MODEL,
    ]

    for raw_value in raw_fallback_lists:
        for model in parse_model_list(raw_value):
            if model not in attempts:
                attempts.append(model)

    return attempts


def openrouter_headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_SITE_NAME,
    }


def extract_openrouter_content(data) -> str:
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    if isinstance(content, list):
        content = "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
        )

    return str(content or "").strip()


def call_openrouter_model(prompt: str, model: str) -> tuple[bool, str, str]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": str(prompt or ""),
            },
        ],
        "temperature": AI_TEMPERATURE,
        "max_tokens": AI_MAX_TOKENS,
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=openrouter_headers(),
            json=payload,
            timeout=OPENROUTER_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return (
                False,
                "",
                f"Model {model} failed with status {response.status_code}: {response.text}",
            )

        data = response.json()
        content = extract_openrouter_content(data)

        if not content:
            return False, "", f"Model {model} returned an empty response. Raw response: {data}"

        return True, content, ""

    except requests.exceptions.Timeout:
        return False, "", f"Model {model} timed out after {OPENROUTER_TIMEOUT_SECONDS} seconds."

    except Exception as error:
        return False, "", f"Model {model} error: {str(error)}"


def generate_with_openrouter(prompt: str, model: str | None = None) -> str:
    if not OPENROUTER_API_KEY:
        return """
OpenRouter is selected, but OPENROUTER_API_KEY is missing.

Required:

AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
LIQUID_THINKING_MODEL=liquid/lfm-2.5-1.2b-thinking:free
LIQUID_INSTRUCT_MODEL=liquid/lfm-2.5-1.2b-instruct:free
OPENROUTER_BACKUP_MODELS=z-ai/glm-5.2,moonshotai/kimi-k2.7-code,nvidia/nemotron-3-ultra-550b-a55b:free,qwen/qwen3.5-35b-a3b,meta-llama/llama-3.3-70b-instruct:free,meta-llama/llama-3.2-3b-instruct:free,openrouter/free
"""

    primary_model = model or choose_liquid_model(prompt)
    model_attempts = build_model_attempts(primary_model)

    errors = []

    for attempt_number, model_name in enumerate(model_attempts, start=1):
        success, content, error_message = call_openrouter_model(prompt, model_name)

        if success:
            if attempt_number == 1:
                return content

            return f"""[AI Backup Used: {model_name}]

{content}"""

        errors.append(error_message)

    return f"""
All AI model attempts failed.

Models tried:
{", ".join(model_attempts)}

Errors:
{chr(10).join(errors)}
"""


def generate_ai_response(prompt: str) -> str:
    if AI_PROVIDER == "openrouter":
        return generate_with_openrouter(prompt)

    return f"""
Invalid AI_PROVIDER value:

{AI_PROVIDER}

Use this setting:

AI_PROVIDER=openrouter

Required variables:

OPENROUTER_API_KEY=your_openrouter_api_key_here
LIQUID_THINKING_MODEL=liquid/lfm-2.5-1.2b-thinking:free
LIQUID_INSTRUCT_MODEL=liquid/lfm-2.5-1.2b-instruct:free
OPENROUTER_BACKUP_MODELS=z-ai/glm-5.2,moonshotai/kimi-k2.7-code,nvidia/nemotron-3-ultra-550b-a55b:free,qwen/qwen3.5-35b-a3b,meta-llama/llama-3.3-70b-instruct:free,meta-llama/llama-3.2-3b-instruct:free,openrouter/free
"""


def ask_ai(prompt: str) -> str:
    """
    Backward-compatible function for app.py.
    Your Streamlit app can call ask_ai(prompt).
    """
    return generate_ai_response(prompt)
