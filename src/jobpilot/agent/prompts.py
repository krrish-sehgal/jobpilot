"""
Prompt strings used by the agent loop.

These are illustrative placeholders written for this demo — they are not
tuned, tested, or derived from any real deployment. Real prompts tend to
be longer, more specific, and shaped by a lot of trial and error; these
are short on purpose, to keep the teaching example readable.
"""

# The system prompt handed to the model at the start of every turn. It
# establishes the assistant's role and reminds it that tools exist and
# should be preferred over guessing.
AGENT_SYSTEM_PROMPT = """\
You are JobPilot, a job-search assistant in a chat conversation.
You help someone find roles that fit them, using the tools available
to you rather than inventing information.

Rules of thumb:
- If you need facts about jobs, call search_jobs. Do not make up listings.
- If you need something the person told you before, call recall_memory.
- If you need details from their resume, call fetch_resume.
- Keep replies short and conversational, like a text message.
- If no tool result answers the question, say so plainly.
"""

# Shown to the model when it is deciding whether it has enough information
# to stop calling tools and answer directly.
AGENT_STOP_CHECK_PROMPT = """\
Look at the tool results gathered so far in this turn. If they are
enough to give the person a useful, specific answer, answer now.
Otherwise, call exactly one more tool that would close the gap.
"""

# Used by the enrichment step (see ingest/enrich.py) to turn a messy
# job posting into a strict structured record.
ENRICH_JOB_PROMPT = """\
You will be given the raw text of a job posting. Extract a structured
record with: role_category, seniority_band, skills (list), location,
pay_range (if stated), and a scam_risk flag (true/false) with a one
line reason. Only use the taxonomy provided to you. If a field is not
present in the text, leave it null — do not guess.
"""

# Used by the matching idea (see docs/architecture.md): instead of
# embedding the job description itself, the model writes a short
# description of the ideal candidate, with company and location removed.
IDEAL_CANDIDATE_PROMPT = """\
Describe the ideal candidate for this role in two or three sentences,
written the way a person might describe themselves. Do not mention the
company name, the city, or the salary. Focus on background, skills,
and the kind of work they would be doing day to day.
"""
