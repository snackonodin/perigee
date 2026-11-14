#!/usr/bin/env bash
. "$(dirname "$0")/env.sh"
hist=coord/progress_history.csv; tot=0; done=0
any() { [ -n "$(find . -name "$1" -not -path '*/node_modules/*' 2>/dev/null | head -1)" ]; }
has() { f=$(find . -name "$1" -not -path '*/node_modules/*' 2>/dev/null | head -1); [ -n "$f" ] && grep -qE "$2" "$f"; }
m() { w=$1; n=$2; shift 2; tot=$((tot+w))
  if "$@" >/dev/null 2>&1; then done=$((done+w)); printf " [x] %-44s %2d\n" "$n" "$w"
  else printf " [ ] %-44s %2d\n" "$n" "$w"; fi; }

m 10 "Engine: 0 spec violations (last eval)"   has last_eval.json '"violations": *0'
m  5 "Engine: z<1.5 baseline admission"        grep -rqE 'z *< *1\.5' $E
m  3 "Spec: cold-start line written"           has context-v2.md '28 valid nights'
m 10 "Backend: auth (register/login)"          grep -rqiE 'def +(register|login)' $B --include=*.py
m 10 "Backend: nightly job calls engine.api"   grep -rq 'engine.api' $B --include=*.py
m  8 "Backend: safety_screen_required wired"   grep -rq safety_screen_required $B --include=*.py
m  3 "Backend: /weekly endpoint"               grep -rqi weekly $B --include=*.py
m  5 "Contract: openapi.json"                  any openapi.json
m  3 "Docs: ARCHITECTURE.md"                   any ARCHITECTURE.md
m  6 "Docs: DESIGN.md (Claude's design system)" any DESIGN.md
m  7 "Frontend: scaffold (package.json)"       test -f $F/package.json
m  8 "Frontend: safety screen"                 grep -rqi safety_screen_required $F/src
m  8 "Frontend: dashboard + chart"             grep -rqi chart $F/src
m 10 "Full suite green (coord/suite.sh)"       bash -c "[ -f coord/last_suite.txt ] && ! grep -qE '^(FAILED|ERROR)' coord/last_suite.txt && grep -q passed coord/last_suite.txt"
m  4 "Demo scenarios exist"                    any scenarios.json
m  4 "Engine demo scenarios pass"              bash -c "grep -q 'scenarios passed' coord/overnight/engine_demo.log 2>/dev/null && ! grep -q FAIL coord/overnight/engine_demo.log"
m  4 "Frontend tests green (overnight)"        bash -c "grep -qE 'Test Files +[0-9]+ passed \\([0-9]+\\)$' coord/overnight/frontend_tests.log"
m  4 "Demo app smoke: 3 personas OK"           bash -c "tail -1 coord/overnight/REPORT.md | grep -q '| ok steady:200,200,200,200,503 drift:200,200,200,200,503 dip:200,200,200,200,503'"
m  4 "Overnight demo cycles ran"               bash -c "[ \$(grep -c '^| 11-' coord/overnight/REPORT.md 2>/dev/null) -ge 3 ]"
m  6 "Frontend bugs from overnight fixed"      bash -c "! grep -qE '^\\| V[0-9]+ .*\\| open \\|' coord/overnight/BUGS.md"
m  3 "Deploy: hosting plan written"            any DEPLOY.md

pct=$((done*100/tot)); w=40; f=$((pct*w/100)); bar=""; i=0
while [ $i -lt $w ]; do if [ $i -lt $f ]; then bar="$bar█"; else bar="$bar░"; fi; i=$((i+1)); done
echo; echo " $bar $pct%"

now=$(date +%s); last=$(tail -1 $hist 2>/dev/null | cut -d, -f2)
[ "$last" != "$done" ] && echo "$now,$done" >> $hist
set -- $(awk -F, -v c=$((now-259200)) '$1>=c{print $1,$2; exit}' $hist)
if [ -n "$1" ] && [ $((now-$1)) -ge 3600 ] && [ "$done" -gt "$2" ]; then
  awk -v n=$now -v t=$1 -v d=$done -v d0=$2 -v tot=$tot 'BEGIN{r=(d-d0)/((n-t)/3600); printf " ETA ~ %.1f days at current pace (%.1f pts/day)\n",(tot-d)/r/24,r*24}'
else echo " ETA: calibrating (needs a milestone to land + >1h of history)"; fi
