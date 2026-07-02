from repp_ai_instructions import (
    GLOBAL_RECRUITING_GUARDRAILS,
    PRE_SCREENER_INSTRUCTIONS,
    INTERVIEW_SCRIPT_GENERATOR_INSTRUCTIONS,
    INTERVIEW_EVALUATOR_INSTRUCTIONS,
    INTERVIEW_SOP_DO_NOT_ASK,
    DEFAULT_ONE_CALL_INTERVIEW_SCRIPT_TEMPLATE,
)


def candidate_to_text(candidate):
    if not candidate:
        return "No candidate information provided."

    try:
        return f"""
Candidate ID:
{candidate[0]}

Candidate Name:
{candidate[1] or "Not specified"}

Location:
{candidate[2] or "Not specified"}

Applied Role:
{candidate[3] or "Not specified"}

Resume Text:
{candidate[4] or "No resume text available."}

Screening Answers:
{candidate[5] or "No screening answers available."}

Portfolio Links:
{candidate[6] or "No portfolio links provided."}

Created At:
{candidate[7] or "Not specified"}

Email:
{candidate[8] or "Not specified"}

Phone:
{candidate[9] or "Not specified"}

Candidate Status:
{candidate[10] or "Not specified"}

Mapped Client ID:
{candidate[11] or "Not specified"}

Mapped Client Name:
{candidate[12] or "Not specified"}

Mapped Client Distance / Need Match Score:
{candidate[13] if len(candidate) > 13 else "Not specified"}
"""
    except Exception:
        return str(candidate)


def client_to_text(client):
    if not client:
        return "No client information provided."

    try:
        return f"""
Client ID:
{client[0]}

Client Name:
{client[1] or "Not specified"}

Role:
{client[2] or "Not specified"}

Location:
{client[3] or "Not specified"}

Client Needs:
{client[4] or "No client needs provided."}

Formatted Client Needs:
{client[9] if len(client) > 9 and client[9] else "No formatted client needs provided."}
"""
    except Exception:
        return str(client)


def client_formatter_prompt(raw_client_notes):
    return f"""
{GLOBAL_RECRUITING_GUARDRAILS}

You are REPP Talent's client-needs formatter.

Your job:
Turn messy client intake notes into a clean, structured recruiting brief that can be used for candidate screening, interview scripts, client matching, and interview evaluation.

Rules:
- Do not invent facts.
- Preserve exact compensation details.
- Preserve exact schedule, availability, hiring radius, service radius, and location requirements.
- Preserve whether gear is provided.
- Preserve employment type.
- Preserve hard requirements and dealbreakers.
- Preserve client wording when possible.
- If a field is missing, write "Not specified."
- Do not over-summarize.
- Do not remove important details.

Output format:

Client Name:
[Client/contact name]

Contact Name:
[Contact name]

Company Name:
[Company name]

Email:
[Email if available]

Monday Doc:
[Monday doc if available]

Role Hiring:
[Role]

Ideal Location for Hire:
[Location]

Compensation Type:
[Compensation type]

Compensation Details:
[Exact compensation details]

Is Gear Provided by the Company:
[Yes / No / Not specified]

Employment Type:
[Employment type]

Hours Per Week:
[Hours]

Specific Availability Requirements:
[Availability]

Essential Character Traits / Values:
[Traits]

Anything Else We Should Know:
[Additional notes]

Hiring Radius:
[Hiring radius]

Green or Experienced:
[Green or experienced preference]

Service Radius:
[Service radius]

Urgency:
[Urgency]

Hard Requirements:
[List hard requirements only.]

Preferences:
[List preferences only.]

Dealbreakers / Watchouts:
[List confirmed dealbreakers or watchouts only.]

Recruiting Summary:
[Short practical summary for REPP recruiters.]

Raw Client Notes:
{raw_client_notes}
"""


def screening_prompt(candidate, client):
    candidate_text = candidate_to_text(candidate)
    client_text = client_to_text(client)

    return f"""
{GLOBAL_RECRUITING_GUARDRAILS}

{PRE_SCREENER_INSTRUCTIONS}

Candidate Information:
{candidate_text}

Mapped Client Information:
{client_text}

Important:
- Evaluate this candidate independently.
- Use the mapped client's actual needs as the standard.
- Use the resume heavily.
- Use screening answers heavily.
- Actively check for competing business risk.
- Actively check for Real Estate license conflict.
- Do not invent concerns.
- If the concern can reasonably be verified in an interview, prefer Proceed to Initial Interview and list it under Interview Focus Areas.
- Do not overpraise.
- Make a real recruiting decision.
"""


def interview_script_prompt(candidate, client):
    candidate_text = candidate_to_text(candidate)
    client_text = client_to_text(client)

    return f"""
{GLOBAL_RECRUITING_GUARDRAILS}

{INTERVIEW_SOP_DO_NOT_ASK}

{INTERVIEW_SCRIPT_GENERATOR_INSTRUCTIONS}

Default Script Template:
{DEFAULT_ONE_CALL_INTERVIEW_SCRIPT_TEMPLATE}

Candidate Information:
{candidate_text}

Mapped Client Information:
{client_text}

Important:
- Generate only the usable interview script.
- Do not evaluate the candidate.
- Do not rank, score, pass, fail, or label the candidate.
- Do not include internal mapping notes.
- Do not mention knowledge files, source files, workbook tabs, or hidden reasoning.
- Use the default script structure and natural Shin-style tone.
- Tailor the questions to the resume, screening answers, mapped client needs, role, compensation, location, schedule, and risks.
- Use exact compensation details from the client information when available.
- Do not invent compensation if it is missing.
- Keep protected-topic rules in mind.
"""


def evaluation_prompt(candidate, client, transcript_text):
    candidate_text = candidate_to_text(candidate)
    client_text = client_to_text(client)

    return f"""
{GLOBAL_RECRUITING_GUARDRAILS}

{INTERVIEW_EVALUATOR_INSTRUCTIONS}

Candidate Information:
{candidate_text}

Mapped Client Information:
{client_text}

Interview Transcript:
{transcript_text}

Important:
- Treat the transcript as primary behavioral evidence.
- Evaluate against the mapped client's actual needs.
- Use resume and screening answers as supporting context only.
- Actively check for competing business risk.
- Actively check for Real Estate license conflict.
- Do not invent concerns.
- Do not overpraise.
- Make a real recruiting decision.
- Use the required output format exactly.
"""
