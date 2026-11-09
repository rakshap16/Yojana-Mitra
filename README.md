# Yojana Mitra: voice-first government scheme finder (Gnani hackathon)

Speak (or type) in English, Hindi or Kannada -> Prisma transcribes -> Evon extracts your profile ->
a deterministic rule engine matches schemes -> Timbre reads the results aloud.

## Run
    pip install -r requirements.txt
    python app.py        # http://localhost:5000

It starts in **demo mode** (browser mic + keyword parsing + browser voice), so you can demo with no keys.

## Go live with Gnani
1. Create your API keys in the Gnani dashboard, copy `.env.example` to `.env`.
2. Fill GNANI_API_KEY and the three URLs from the API Docs.
3. Open `gnani.py` and adjust the three `# ADAPT` blocks (headers, payload, response field names).
The header badge switches from "Demo mode" to "Gnani voice live".

## Honest limits
- Scheme rules are simplified summaries of 15 schemes; verify against official sources before the demo.
- Hindi and Kannada copy should be reviewed by a native speaker.
- Eligibility is decided by code, not by the LLM, so results are explainable and consistent.
