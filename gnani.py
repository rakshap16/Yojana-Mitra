"""Thin adapter around Gnani's Prisma (STT), Evon (reasoning) and Timbre (TTS).

I could not verify Gnani's exact request/response formats, so each function
below is a small, clearly marked adapter. Open the API Docs from your hackathon
email and adjust the three `# ADAPT` blocks. Everything else in the app
works unchanged. If a URL is empty, the function raises NotConfigured and the
app falls back to demo mode.
"""
import json, os
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("GNANI_API_KEY", "")
STT_URL = os.getenv("GNANI_STT_URL", "")
TTS_URL = os.getenv("GNANI_TTS_URL", "")
LLM_URL = os.getenv("GNANI_LLM_URL", "")
LLM_MODEL = os.getenv("GNANI_LLM_MODEL", "evon")
LANG_CODES = {"en": "en-IN", "hi": "hi-IN", "kn": "kn-IN"}


class NotConfigured(Exception):
    pass


def status():
    return {"stt": bool(KEY and STT_URL), "tts": bool(KEY and TTS_URL), "llm": bool(KEY and LLM_URL)}


def transcribe(audio_bytes: bytes, mimetype: str, lang: str) -> str:
    """Prisma speech-to-text."""
    if not (KEY and STT_URL):
        raise NotConfigured("stt")
    # ADAPT: header names, field names and response shape per Prisma docs.
    r = requests.post(
        STT_URL,
        headers={"Authorization": f"Bearer {KEY}"},
        files={"audio": ("speech", audio_bytes, mimetype)},
        data={"language": LANG_CODES.get(lang, "en-IN")},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("transcript") or r.json().get("text", "")


def speak(text: str, lang: str):
    """Timbre text-to-speech. Returns (audio_bytes, mimetype)."""
    if not (KEY and TTS_URL):
        raise NotConfigured("tts")
    # ADAPT: payload keys, voice name and audio format per Timbre docs.
    r = requests.post(
        TTS_URL,
        headers={"Authorization": f"Bearer {KEY}"},
        json={"text": text, "language": LANG_CODES.get(lang, "en-IN")},
        timeout=30,
    )
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "audio/wav")


def chat(system: str, user: str) -> str:
    """Evon reasoning. Assumes an OpenAI-style chat endpoint (common for hosted open models)."""
    if not (KEY and LLM_URL):
        raise NotConfigured("llm")
    # ADAPT: if Evon uses a different schema, change payload and the return line.
    r = requests.post(
        LLM_URL,
        headers={"Authorization": f"Bearer {KEY}"},
        json={
            "model": LLM_MODEL,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def extract_profile_json(text: str, lang: str) -> dict:
    """Ask Evon to turn a spoken self-description into a profile dict."""
    system = (
        "Extract facts from the user's sentence (any of English, Hindi, Kannada). "
        "Reply with ONLY JSON: {\"age\":int|null,\"gender\":\"female\"|\"male\"|null,"
        "\"state\":string|null,\"occupation\":\"farmer\"|\"business\"|\"artisan\"|\"student\"|\"labour\"|\"homemaker\"|\"other\"|null,"
        "\"income\":int|null (annual rupees),\"bpl\":true|false|null,\"girl_child\":true|false|null}. "
        "Use null when not stated. Never guess."
    )
    raw = chat(system, text)
    raw = raw[raw.find("{"): raw.rfind("}") + 1]
    return json.loads(raw)
