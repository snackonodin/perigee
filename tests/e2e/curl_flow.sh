#!/usr/bin/env bash
# curl_flow.sh: end-to-end demo flow against a running API (OPS-7). Doubles as the demo rehearsal.
#   health → openapi → signup → login → /me → 401 without token → consents → instruments →
#   daily check-in (no safety) → PHQ-9 with item 9 = 1 (safety screen) → malformed PHQ-9 still
#   shows safety → guidance (unknown flag 404) → /today → refresh → logout → old refresh rejected →
#   delete account → login rejected
# Usage: tests/e2e/curl_flow.sh [--keep]     (--keep: do not delete the test account)
# Env:   BASE_URL (default http://127.0.0.1:8000), PYTHON (default python3), CURL_TIMEOUT (10)
# Output: one PASS/FAIL/SKIP line per step. SKIP = the route is not in /openapi.json yet.
# Exit:  0 no FAIL · 1 any FAIL · 2 API unreachable. Tokens and passwords are never printed.
# All answers are synthetic; the item-9 answer exists only to exercise the safety path.
set -uo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"; BASE_URL="${BASE_URL%/}"
PY="${PYTHON:-python3}"
TIMEOUT="${CURL_TIMEOUT:-10}"
KEEP=0; [[ "${1:-}" == "--keep" ]] && KEEP=1
[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { sed -n 2,11p "$0"; exit 0; }
command -v curl >/dev/null || { echo "needs curl" >&2; exit 2; }
command -v "$PY" >/dev/null || { echo "needs python3 (set PYTHON)" >&2; exit 2; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/curlflow.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
BODY="$TMP/body.json"; OPENAPI="$TMP/openapi.json"
CODE=""; MS=""; N=0; FAILS=0; PASSES=0; SKIPS=0

# req METHOD PATH [JSON] [TOKEN] → CODE, MS, $BODY
req() {
  local args=(-s -o "$BODY" -w '%{http_code} %{time_total}' -X "$1" --max-time "$TIMEOUT"
              -H 'Accept: application/json')
  [[ -n "${3:-}" ]] && args+=(-H 'Content-Type: application/json' --data "$3")
  [[ -n "${4:-}" ]] && args+=(-H "Authorization: Bearer $4")
  local out; out="$(curl "${args[@]}" "$BASE_URL$2" 2>/dev/null)" || out="000 0"
  CODE="${out%% *}"; MS="$(awk -v t="${out##* }" 'BEGIN{printf "%d", t*1000}')"
}

# jget PATH.TO.FIELD → prints the value from $BODY (JSON for dict/list/bool, "" if missing)
jget() {
  "$PY" - "$BODY" "$1" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
for k in sys.argv[2].split(".") if sys.argv[2] else []:
    if isinstance(d, list) and k.isdigit() and int(k) < len(d):
        d = d[int(k)]
    elif isinstance(d, dict):
        d = d.get(k)
    else:
        d = None
print("" if d is None else d if isinstance(d, str) else json.dumps(d))
PY
}

# has_route METHOD PATH → 0 if /openapi.json lists it
has_route() {
  "$PY" - "$OPENAPI" "$1" "$2" <<'PY' 2>/dev/null
import json, sys
try:
    paths = json.load(open(sys.argv[1])).get("paths", {})
except Exception:
    sys.exit(1)
sys.exit(0 if sys.argv[3] in paths and sys.argv[2].lower() in paths[sys.argv[3]] else 1)
PY
}

# result NAME OK(0/1) DETAIL
result() {
  N=$((N + 1))
  if [[ "$2" -eq 0 ]]; then PASSES=$((PASSES + 1)); printf 'PASS %02d %-28s %s %5sms %s\n' "$N" "$1" "$CODE" "$MS" "${3:-}"
  else FAILS=$((FAILS + 1)); printf 'FAIL %02d %-28s %s %5sms %s\n' "$N" "$1" "$CODE" "$MS" "${3:-}"
    [[ -s "$BODY" ]] && printf '     body: %s\n' "$(head -c 200 "$BODY" | tr '\n' ' ')"; fi
}
skip() { N=$((N + 1)); SKIPS=$((SKIPS + 1)); printf 'SKIP %02d %-28s %s\n' "$N" "$1" "${2:-route not in /openapi.json yet}"; }
# need METHOD PATH NAME: returns 1 (and prints SKIP) when the route is not mounted
need() { has_route "$1" "$2" && return 0; skip "$3"; return 1; }
is() { [[ "$1" == "$2" ]]; }

echo "curl_flow against $BASE_URL"

# 1-2. reachability
req GET /api/v1/health
if [[ "$CODE" == "000" ]]; then echo "FAIL API unreachable at $BASE_URL (start it, or set BASE_URL)"; exit 2; fi
result "health" "$(is "$CODE" 200; echo $?)" "status=$(jget status)"
req GET /openapi.json; cp "$BODY" "$OPENAPI" 2>/dev/null
result "openapi" "$(is "$CODE" 200; echo $?)" "paths=$("$PY" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["paths"]))' "$OPENAPI" 2>/dev/null)"

RAND="$("$PY" -c 'import secrets; print(secrets.token_hex(4))')"
EMAIL="${E2E_EMAIL:-e2e-$RAND@example.invalid}"
PW="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(18))')"
CRED="{\"email\":\"$EMAIL\",\"password\":\"$PW\"}"
ACCESS=""; REFRESH=""; USER_ID=""

# 3-5. accounts
if need POST /api/v1/auth/signup "signup"; then
  req POST /api/v1/auth/signup "$CRED"
  USER_ID="$(jget user_id)"
  result "signup" "$(is "$CODE" 201; echo $?)" "user=${USER_ID:0:8}…"
fi
if need POST /api/v1/auth/login "login"; then
  req POST /api/v1/auth/login "$CRED"
  ACCESS="$(jget access_token)"; REFRESH="$(jget refresh_token)"
  ok=1; [[ "$CODE" == 200 && -n "$ACCESS" && -n "$REFRESH" ]] && ok=0
  result "login" "$ok" "tokens=$([[ -n "$ACCESS" ]] && echo yes || echo no)"
fi
if need GET /api/v1/me "me"; then
  req GET /api/v1/me "" "$ACCESS"
  ok=1; [[ "$CODE" == 200 && "$(jget id)" == "$USER_ID" && -n "$USER_ID" ]] && ok=0
  result "me (own user)" "$ok"
  req GET /api/v1/me
  result "me without token → 401" "$(is "$CODE" 401; echo $?)"
fi
if need PUT /api/v1/me/consents "consents"; then
  req PUT /api/v1/me/consents '{"scopes":{"checkins":true,"survey_answers":true},"policy_version":"e2e-1"}' "$ACCESS"
  result "consents granted" "$(is "$CODE" 200; echo $?)"
fi

# 6-9. surveys + safety
if need GET /api/v1/instruments "instruments"; then
  req GET /api/v1/instruments "" "$ACCESS"
  ok=1; [[ "$CODE" == 200 ]] && grep -q '"phq9"' "$BODY" && grep -q '"daily_am"' "$BODY" && ok=0
  hint=""; [[ "$(cat "$BODY")" == "[]" ]] && hint="catalog empty: the API DB never ran surveys.load_catalog"
  result "instruments (phq9, daily_am)" "$ok" "$hint"
  VERS="$("$PY" -c 'import json,sys
for i in json.load(open(sys.argv[1])):
    print(i.get("id", ""), i.get("version", ""), sep="=")' "$BODY" 2>/dev/null)"
fi
# ver ID → ',"instrument_version":"<v>"' from the catalog, or nothing (the API then decides)
ver() { local v; v="$(printf '%s\n' "${VERS:-}" | awk -F= -v id="$1" '$1==id{print $2; exit}')"
        [[ -n "$v" ]] && printf ',"instrument_version":"%s"' "$v"; }
if need POST /api/v1/responses "check-in + safety"; then
  req POST /api/v1/responses '{"instrument_id":"daily_am"'"$(ver daily_am)"',"answers":{"sleep_quality":3,"energy":3,"mood":3}}' "$ACCESS"
  ok=1; [[ "$CODE" == 200 && "$(jget ok)" == true && "$(jget safety.show)" == false ]] && ok=0
  result "daily check-in, no safety" "$ok" "stored=$(jget stored)"

  PHQ9='{"instrument_id":"phq9"'"$(ver phq9)"',"answers":{"phq9_1":0,"phq9_2":0,"phq9_3":0,"phq9_4":0,"phq9_5":0,"phq9_6":0,"phq9_7":0,"phq9_8":0,"phq9_9":1}}'
  req POST /api/v1/responses "$PHQ9" "$ACCESS"
  ok=1; [[ "$CODE" == 200 && "$(jget safety.show)" == true && -n "$(jget safety.reason)" ]] && ok=0
  result "PHQ-9 item 9 → safety screen" "$ok" "show=$(jget safety.show) resources=$("$PY" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["safety"]["resources"]))' "$BODY" 2>/dev/null)"

  BAD='{"instrument_id":"phq9"'"$(ver phq9)"',"answers":{"phq9_1":"oops","phq9_9":1}}'
  req POST /api/v1/responses "$BAD" "$ACCESS"
  ok=1; [[ "$(jget safety.show)" == true && "$(jget ok)" != true ]] && ok=0
  result "malformed PHQ-9 still safety" "$ok" "ok=$(jget ok) error=$(jget error)"
fi

# 10-11. read side
if need GET /api/v1/guidance "guidance"; then
  req GET "/api/v1/guidance?flag_id=00000000-0000-0000-0000-000000000000" "" "$ACCESS"
  result "guidance, unknown flag → 404" "$(is "$CODE" 404; echo $?)"
fi
if need GET /api/v1/today "today"; then
  req GET /api/v1/today "" "$ACCESS"
  ok=1; [[ "$CODE" == 200 ]] && "$PY" -c 'import json,sys; assert isinstance(json.load(open(sys.argv[1])), dict)' "$BODY" 2>/dev/null && ok=0
  result "today" "$ok"
fi

# 12-14. token lifecycle
if need POST /api/v1/auth/refresh "refresh"; then
  req POST /api/v1/auth/refresh "{\"refresh_token\":\"$REFRESH\"}"
  NEW_REFRESH="$(jget refresh_token)"; NEW_ACCESS="$(jget access_token)"
  ok=1; [[ "$CODE" == 200 && -n "$NEW_REFRESH" ]] && ok=0
  result "refresh" "$ok"
  [[ -n "$NEW_REFRESH" ]] && { REFRESH="$NEW_REFRESH"; ACCESS="$NEW_ACCESS"; }
fi
if need POST /api/v1/auth/logout "logout"; then
  req POST /api/v1/auth/logout "{\"refresh_token\":\"$REFRESH\"}" "$ACCESS"
  result "logout" "$(is "$CODE" 204; echo $?)"
  req POST /api/v1/auth/refresh "{\"refresh_token\":\"$REFRESH\"}"
  result "revoked refresh → 401" "$(is "$CODE" 401; echo $?)"
fi

# 15-16. delete account (unless --keep)
if [[ $KEEP -eq 1 ]]; then skip "delete account" "--keep: $EMAIL left in place"
elif need DELETE /api/v1/me "delete account"; then
  req POST /api/v1/auth/login "$CRED"; ACCESS="$(jget access_token)"
  req DELETE /api/v1/me "" "$ACCESS"
  result "delete account" "$(is "$CODE" 204; echo $?)"
  req POST /api/v1/auth/login "$CRED"
  result "login after delete → 401" "$(is "$CODE" 401; echo $?)"
fi

echo "summary: pass=$PASSES fail=$FAILS skip=$SKIPS base=$BASE_URL"
[[ $FAILS -eq 0 ]]
