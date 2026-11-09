import json, re, sqlite3, time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, Response

import gnani

BASE = Path(__file__).parent
SCHEMES = json.loads((BASE / "data" / "schemes.json").read_text(encoding="utf-8"))
DB = BASE / "queries.db"

app = Flask(__name__, static_folder="static", static_url_path="/static")


# ---------- storage (SQLite: anonymous query log, no personal text kept) ----------
def db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS queries (ts REAL, lang TEXT, matched INTEGER, via TEXT)")
    return con


# ---------- eligibility engine ----------
def check(cond: dict, p: dict):
    """Return 'yes' | 'no' | 'unknown' for one rule dict (all conditions must hold)."""
    result = "yes"
    for key, want in cond.items():
        if key == "any_of":
            sub = [check(c, p) for c in want]
            r = "yes" if "yes" in sub else ("unknown" if "unknown" in sub else "no")
        else:
            have = {
                "min_age": p.get("age"), "max_age": p.get("age"), "gender": p.get("gender"),
                "occupation": p.get("occupation"), "bpl": p.get("bpl"),
                "girl_child": p.get("girl_child"), "max_income": p.get("income"),
            }[key]
            if have is None:
                r = "unknown"
            elif key == "min_age":
                r = "yes" if have >= want else "no"
            elif key == "max_age":
                r = "yes" if have <= want else "no"
            elif key == "max_income":
                r = "yes" if have <= want else "no"
            elif key == "occupation":
                r = "yes" if have in want else "no"
            else:
                r = "yes" if have == want else "no"
        if r == "no":
            return "no"
        if r == "unknown":
            result = "unknown"
    return result


def match(profile: dict):
    out = []
    state = (profile.get("state") or "").strip().lower()
    for s in SCHEMES:
        if s["state"] and state and s["state"].lower() != state:
            continue
        if s["state"] and not state:
            r = "unknown"
            if check(s["rule"], profile) == "no":
                continue
        else:
            r = check(s["rule"], profile)
            if r == "no":
                continue
        out.append({**s, "status": "eligible" if r == "yes" else "check"})
    out.sort(key=lambda x: x["status"] != "eligible")
    return out


# ---------- demo-mode profile parsing (works offline, 3 languages) ----------
KW = {
    "female": ["woman", "female", "lady", "girl", "महिला", "औरत", "स्त्री", "ಮಹಿಳೆ", "ಹೆಂಗಸು"],
    "male": [" man ", " man,", "male", "boy", "पुरुष", "आदमी", "ಪುರುಷ", "ಗಂಡಸು"],
    "farmer": ["farmer", "farming", "agricultur", "किसान", "खेती", "ರೈತ", "ಕೃಷಿ"],
    "business": ["shop", "business", "trader", "vendor", "दुकान", "व्यापार", "ವ್ಯಾಪಾರ", "ಅಂಗಡಿ"],
    "artisan": ["artisan", "carpenter", "potter", "weaver", "tailor", "कारीगर", "बढ़ई", "कुम्हार", "ಕುಶಲ", "ಬಡಗಿ", "ನೇಕಾರ"],
    "student": ["student", "छात्र", "विद्यार्थी", "ವಿದ್ಯಾರ್ಥಿ"],
    "labour": ["labour", "labor", "worker", "मजदूर", "ಕೂಲಿ"],
    "homemaker": ["homemaker", "housewife", "गृहिणी", "ಗೃಹಿಣಿ"],
    "bpl": ["bpl", "ration card", "below poverty", "राशन कार्ड", "गरीबी रेखा", "ಪಡಿತರ", "ಬಿಪಿಎಲ್"],
    "karnataka": ["karnataka", "bengaluru", "bangalore", "mysuru", "कर्नाटक", "ಕರ್ನಾಟಕ", "ಬೆಂಗಳೂರು"],
    "girl_child": ["daughter", "girl child", "बेटी", "ಮಗಳು", "ಹೆಣ್ಣು ಮಗು"],
}
DIGITS = str.maketrans("०१२३४५६७८९೦೧೨೩೪೫೬೭೮೯", "01234567890123456789")


def has(text, key):
    return any(k in text for k in KW[key])


def parse_rules(text: str) -> dict:
    t = " " + text.lower().translate(DIGITS) + " "
    p = {"age": None, "gender": None, "state": None, "occupation": None, "income": None, "bpl": None, "girl_child": None}
    m = re.search(r"(\d{1,2})\s*(?:years|year|yrs|साल|वर्ष|ವರ್ಷ)", t) or re.search(r"\bage\D{0,10}(\d{1,2})\b", t) or re.search(r"\b(\d{2})\b", t)
    if m and 5 <= int(m.group(1)) <= 99:
        p["age"] = int(m.group(1))
    p["gender"] = "female" if has(t, "female") else ("male" if has(t, "male") else None)
    for occ in ("farmer", "artisan", "business", "student", "labour", "homemaker"):
        if has(t, occ):
            p["occupation"] = occ
            break
    if p["occupation"] == "homemaker" and not p["gender"]:
        p["gender"] = "female"
    if has(t, "bpl"):
        p["bpl"] = True
    if has(t, "karnataka"):
        p["state"] = "Karnataka"
    if has(t, "girl_child"):
        p["girl_child"] = True
    inc = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|लाख|ಲಕ್ಷ)", t)
    if inc:
        p["income"] = int(float(inc.group(1)) * 100000)
    return p


# ---------- routes ----------
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/status")
def api_status():
    s = gnani.status()
    s["demo"] = not any(s.values())
    return jsonify(s)


@app.post("/api/parse")
def api_parse():
    body = request.get_json(force=True)
    text, lang = body.get("text", ""), body.get("lang", "en")
    via = "rules"
    try:
        profile = gnani.extract_profile_json(text, lang)
        via = "evon"
    except Exception:  # not configured or call failed -> rules
        profile = parse_rules(text)
    return jsonify({"profile": profile, "via": via})


@app.post("/api/match")
def api_match():
    body = request.get_json(force=True)
    profile, lang = body.get("profile", {}), body.get("lang", "en")
    results = match(profile)
    con = db()
    con.execute("INSERT INTO queries VALUES (?,?,?,?)", (time.time(), lang, len(results), body.get("via", "form")))
    con.commit(); con.close()
    return jsonify({"results": results})


@app.post("/api/stt")
def api_stt():
    audio = request.files.get("audio")
    lang = request.form.get("lang", "en")
    try:
        return jsonify({"text": gnani.transcribe(audio.read(), audio.mimetype or "audio/webm", lang)})
    except gnani.NotConfigured:
        return jsonify({"error": "demo"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.post("/api/tts")
def api_tts():
    body = request.get_json(force=True)
    try:
        audio, mime = gnani.speak(body.get("text", ""), body.get("lang", "en"))
        return Response(audio, mimetype=mime)
    except gnani.NotConfigured:
        return jsonify({"error": "demo"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5000)
