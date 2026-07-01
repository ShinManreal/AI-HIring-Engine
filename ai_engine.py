import os
from dotenv import load_dotenv

load_dotenv()


AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250514")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")


SYSTEM_PROMPT = """
You are an expert recruiting assistant for REPP Talent.

You help format client hiring needs, screen candidates, create tailored interview scripts,
match candidates to clients, parse resumes, and evaluate interview transcripts.

Recruiting standards:
- Be structured, practical, strict, and clear.
- Do not overpraise candidates.
- Do not invent facts.
- Prioritize client-specific needs.
- Use resume, screening answers, client needs, and transcript evidence.
- Surface risks early.
- Make useful recruiting judgments.
"""


def generate_with_openai(prompt):
    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            return """
OpenAI is selected, but OPENAI_API_KEY is missing.

How to fix:
Add this to your Render environment variables:

AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.5

Then redeploy.
"""

        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=prompt,
            temperature=0.2,
            max_output_tokens=4000
        )

        return response.output_text.strip()

    except Exception as error:
        return f"""
OpenAI AI engine is not available right now.

Selected provider:
OpenAI

Model:
{OPENAI_MODEL}

Reason:
{str(error)}

How to fix:
1. Check that OPENAI_API_KEY is correct in Render environment variables.
2. Check that openai is installed:
   pip install openai
3. Check that the model name is valid.
4. Redeploy Render.

Temporary result:
The app did not crash, but OpenAI output could not be generated.
"""


def generate_with_ollama(prompt):
    try:
        import ollama

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            options={
                "temperature": 0.2
            }
        )

        return response["message"]["content"]

    except Exception as error:
        return f"""
AI engine is not available right now.

Selected provider:
Ollama

Reason:
{str(error)}

Most likely cause:
Ollama is not running in this environment.

How to fix:
1. Open a new terminal.
2. Run:
   ollama serve
3. In another terminal, run:
   ollama pull {OLLAMA_MODEL}
4. Restart Streamlit.

Temporary result:
The app did not crash, but AI output could not be generated.
"""


def generate_with_claude(prompt):
    try:
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            return """
Claude is selected, but ANTHROPIC_API_KEY is missing.

How to fix:
Add this to your environment variables:

ANTHROPIC_API_KEY=your_anthropic_api_key_here
AI_PROVIDER=claude
CLAUDE_MODEL=claude-sonnet-4-5-20250514

Then restart or redeploy.
"""

        client = Anthropic(api_key=api_key)

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        text_parts = []

        for content_block in message.content:
            if hasattr(content_block, "text"):
                text_parts.append(content_block.text)

        return "\n".join(text_parts).strip()

    except Exception as error:
        return f"""
Claude AI engine is not available right now.

Selected provider:
Claude

Model:
{CLAUDE_MODEL}

Reason:
{str(error)}

How to fix:
1. Check that ANTHROPIC_API_KEY is correct.
2. Check that anthropic is installed:
   pip install anthropic
3. Check that the model name is valid.
4. Restart or redeploy.

Temporary result:
The app did not crash, but Claude output could not be generated.
"""


def generate_ai_response(prompt):
    if AI_PROVIDER == "openai":
        return generate_with_openai(prompt)

    if AI_PROVIDER == "claude":
        return generate_with_claude(prompt)

    if AI_PROVIDER == "ollama":
        return generate_with_ollama(prompt)

    return f"""
Invalid AI_PROVIDER value:

{AI_PROVIDER}

Use one of these:

AI_PROVIDER=openai
AI_PROVIDER=claude
AI_PROVIDER=ollama
"""


def ask_ai(prompt):
    return generate_ai_response(prompt)