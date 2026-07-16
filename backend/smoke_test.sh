#!/usr/bin/env bash
#
# smoke_test.sh — one-command test for Components 5 & 6.
#
# Runs Component 5 unit tests, boots the server on a free port, then exercises
# /health, /upload (happy path), /history, /analysis/{id}, and the error paths.
# Cleans up the server and temp files on exit.
#
# Usage:
#   ./smoke_test.sh            # picks port 8001 by default
#   PORT=8055 ./smoke_test.sh  # override the port
#
set -u

cd "$(dirname "$0")" || exit 1

PORT="${PORT:-8001}"
BASE="http://localhost:${PORT}"
TMPDIR="$(mktemp -d)"
SERVER_PID=""

pass() { printf "  \033[32mPASS\033[0m  %s\n" "$1"; }
fail() { printf "  \033[31mFAIL\033[0m  %s\n" "$1"; FAILURES=$((FAILURES + 1)); }
FAILURES=0

cleanup() {
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

# Assert that an HTTP call returns the expected status code.
# args: <description> <expected_code> <curl args...>
check_code() {
  local desc="$1" expected="$2"; shift 2
  local code
  code="$(curl -s -o "$TMPDIR/body" -w "%{http_code}" "$@")"
  if [ "$code" = "$expected" ]; then pass "$desc (HTTP $code)"; else
    fail "$desc — expected $expected, got $code"; fi
}

echo "=============================================="
echo " Component 5 & 6 smoke test"
echo "=============================================="

# ---- 1. Component 5 unit tests --------------------------------------------
echo ""
echo "[1/5] Component 5 unit tests"
if python -W ignore -m output.test_redlines >"$TMPDIR/unit.log" 2>&1; then
  pass "output.test_redlines"
else
  fail "output.test_redlines"; cat "$TMPDIR/unit.log"
fi

# ---- 2. Boot the server ----------------------------------------------------
echo ""
echo "[2/5] Starting server on port ${PORT}"
uvicorn main:app --port "$PORT" --log-level warning >"$TMPDIR/server.log" 2>&1 &
SERVER_PID=$!

# Wait up to ~15s for /health to answer.
UP=0
for _ in $(seq 1 30); do
  if curl -s "$BASE/health" >/dev/null 2>&1; then UP=1; break; fi
  sleep 0.5
done
if [ "$UP" = 1 ]; then pass "server is up"; else
  fail "server did not start — see below"; cat "$TMPDIR/server.log"; exit 1
fi

# ---- 3. Happy path: /health, /upload, /history, /analysis ------------------
echo ""
echo "[3/5] Endpoints (happy path)"

check_code "/health" 200 "$BASE/health"

printf "MASTER SERVICES AGREEMENT\nSection 4.1 net 30 days.\n" > "$TMPDIR/MSA.pdf"
printf "STATEMENT OF WORK\nSection 2.2 45 days.\n"            > "$TMPDIR/SOW.pdf"

check_code "POST /upload (both files)" 200 \
  -X POST "$BASE/upload" \
  -F "msa_file=@$TMPDIR/MSA.pdf" -F "sow_file=@$TMPDIR/SOW.pdf"

# Validate the upload payload contents.
python -W ignore - "$TMPDIR/body" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
ok = True
def want(cond, label):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + label)
    ok = ok and cond
s = d.get("summary", {})
want(s.get("blocker") == 1, "1 BLOCKER (missing doc)")
want(s.get("high") == 4, "4 HIGH risks")
want(any("Schedule 1" in m.get("referenced_document","") for m in d.get("missing_docs", [])),
     "Schedule 1 flagged as missing")
want(d.get("graph", {}).get("circular_references"), "circular reference present")
want(d.get("results", [{}])[0].get("severity") == "BLOCKER", "results sorted BLOCKER-first")
r1 = next((r for r in d.get("risks", []) if r.get("risk_id") == "RISK-001"), {})
want(bool(r1.get("suggested_text")), "RISK-001 has a redline suggestion")
sys.exit(0 if ok else 1)
PY
[ $? -eq 0 ] && pass "upload payload contents" || fail "upload payload contents"

check_code "GET /history" 200 "$BASE/history"
check_code "GET /analysis/1" 200 "$BASE/analysis/1"

# ---- 4. Error paths --------------------------------------------------------
echo ""
echo "[4/5] Error handling"

check_code "one file only -> 400" 400 \
  -X POST "$BASE/upload" -F "msa_file=@$TMPDIR/MSA.pdf"

printf "x" > "$TMPDIR/pic.jpg"
check_code "wrong file type -> 400" 400 \
  -X POST "$BASE/upload" \
  -F "msa_file=@$TMPDIR/pic.jpg" -F "sow_file=@$TMPDIR/SOW.pdf"

check_code "unknown analysis -> 404" 404 "$BASE/analysis/999"

# ---- 5. Summary ------------------------------------------------------------
echo ""
echo "[5/5] Result"
if [ "$FAILURES" -eq 0 ]; then
  printf "\033[32mAll smoke tests passed.\033[0m\n"
  exit 0
else
  printf "\033[31m%d check(s) failed.\033[0m\n" "$FAILURES"
  exit 1
fi
