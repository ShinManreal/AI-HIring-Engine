import ollama


OLLAMA_MODEL = "qwen2.5:7b"


def generate_ai_response(prompt):
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert recruiting assistant for REPP Talent. "
                    "You help format client hiring needs, screen candidates, "
                    "create tailored interview scripts, and evaluate interview transcripts. "
                    "Be structured, practical, strict, and do not overpraise candidates."
                )
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


def ask_ai(prompt):
    return generate_ai_response(prompt)