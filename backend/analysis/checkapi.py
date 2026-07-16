"""
check_api_connection.py

One-time sanity check: "is my GROQ_API_KEY actually working?"

This does NOT hardcode any expected answer — it sends a real, generic
prompt to the real Groq API through the SAME code path
(contradiction_detector._call_gemini_raw) that the pipeline uses, and just
tells you plainly what happened at each step. That way, if something is
wrong, you know WHICH step broke (env var missing, network blocked, bad
key, bad model name, JSON parsing) instead of guessing.

Usage:
    pip install python-dotenv --break-system-packages   # if not installed
    # create a .env file in this folder with: GROQ_API_KEY=your_key_here
    python check_api_connection.py

Run this from inside backend/analysis/ (same folder as contradiction_detector.py).
"""
import os
import sys

def main():
    print("=" * 60)
    print("STEP 1: Loading .env file (if present)")
    print("=" * 60)
    try:
        from dotenv import load_dotenv
        loaded = load_dotenv()
        print(f".env loaded: {loaded}  (False just means no .env file found "
              f"in this folder — that's fine if you export the var another way)")
    except ImportError:
        print("python-dotenv not installed — run: pip install python-dotenv --break-system-packages")
        print("Continuing anyway, in case GROQ_API_KEY is set some other way (export, shell profile, etc).")

    print()
    print("=" * 60)
    print("STEP 2: Checking if GROQ_API_KEY is visible to this process")
    print("=" * 60)
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        print("❌ GROQ_API_KEY is NOT set in this process's environment.")
        print("   Fix: create a `.env` file next to this script containing:")
        print("       GROQ_API_KEY=your_actual_key_here")
        print("   (Never commit this file — add .env to .gitignore.)")
        sys.exit(1)
    else:
        print(f"✅ GROQ_API_KEY found (starts with '{key[:4]}...', length {len(key)}).")

    print()
    print("=" * 60)
    print("STEP 3: Making a real call to the Groq API")
    print("=" * 60)
    try:
        from contradiction_detector import _call_gemini_raw
    except ImportError as e:
        print(f"❌ Could not import _call_gemini_raw: {e}")
        print("   Make sure you're running this from inside backend/analysis/.")
        sys.exit(1)

    # Deliberately generic — not tied to any specific dataset/example, so
    # this only proves connectivity + JSON compliance, nothing else.
    test_prompt = (
        "Respond with ONLY this exact JSON object, nothing else, no markdown fences: "
        '{"status": "ok", "received": true}'
    )

    raw = _call_gemini_raw(test_prompt)

    if raw is None:
        print("❌ _call_gemini_raw returned None — the call failed.")
        print("   Check the logged warning/error above this line for the real reason")
        print("   (common causes: invalid key, no network, model name rejected,")
        print("   quota exceeded, request timed out).")
        sys.exit(1)

    print("✅ Got a response back from the API.")
    print(f"   Raw response: {raw!r}")

    print()
    print("=" * 60)
    print("STEP 4: Checking the response parses as JSON")
    print("=" * 60)
    import json
    import re
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        parsed = json.loads(cleaned)
        print(f"✅ Parsed successfully: {parsed}")
        print()
        print("Everything works end-to-end. Your pipeline should run fine")
        print("against a real dataset now — this only checked connectivity,")
        print("not your actual contradiction/override/financial logic")
        print("(that's what test_detector.py already covers offline).")
    except json.JSONDecodeError as e:
        print(f"⚠️  Got a response, but it wasn't clean JSON: {e}")
        print("   This is exactly the case your retry-once logic in")
        print("   contradiction_detector.py is built to handle — not a")
        print("   blocker, just noting it so you're not surprised.")


if __name__ == "__main__":
    main()