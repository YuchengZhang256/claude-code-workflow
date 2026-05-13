#!/usr/bin/env bash
# Canary self-check for proof-audit.
#
# Runs the 5 known-buggy minimal proofs through gpt-5.5 + xhigh (via codex exec
# with --output-schema gap.schema.json) and checks how many produce the expected
# gap_type. proof-audit Phase 2 must see at least 3/5 hit before continuing.
#
# Usage:
#   bash run_canary.sh            # run all 5, write canary_report.json
#   bash run_canary.sh K1-DCT     # single canary id
#
# Cost: ~$1 total on gpt-5.5 xhigh (~16k tokens each).

set -euo pipefail

SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCHEMA="$SKILL_ROOT/schema/gap.schema.json"
SNIPPETS="$SKILL_ROOT/canary/snippets.json"
OUT_DIR="${OUT_DIR:-$SKILL_ROOT/canary/runs/$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT_DIR"

CANARY_FILTER="${1:-}"

require() { command -v "$1" >/dev/null 2>&1 || { echo "missing $1" >&2; exit 2; }; }
require codex
require jq
require python3

# Verify codex CLI works (the XProtect-deletion gotcha)
if ! codex --version >/dev/null 2>&1; then
  echo "ERROR: codex CLI is broken. Re-sign the binary:" >&2
  echo "  npm install -g @openai/codex@0.130.0 --force" >&2
  echo "  codesign --force --sign - /opt/homebrew/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/codex/codex" >&2
  exit 3
fi

report="$OUT_DIR/canary_report.json"
echo '{"runs":[]}' > "$report"

ids=$(jq -r '.canaries[].canary_id' "$SNIPPETS")
total=0
hits=0
for id in $ids; do
  if [ -n "$CANARY_FILTER" ] && [ "$id" != "$CANARY_FILTER" ]; then continue; fi
  total=$((total+1))
  echo "[canary] $id ..." >&2

  claim_id=$(jq -r ".canaries[] | select(.canary_id==\"$id\") | .claim_id" "$SNIPPETS")
  claim_text=$(jq -r ".canaries[] | select(.canary_id==\"$id\") | .claim_text" "$SNIPPETS")
  expected_array=$(jq -c ".canaries[] | select(.canary_id==\"$id\") | .expected_gap_types" "$SNIPPETS")
  min_sev=$(jq -r ".canaries[] | select(.canary_id==\"$id\") | .expected_severity_min" "$SNIPPETS")

  prompt_file="$OUT_DIR/${id}.prompt.txt"
  out_file="$OUT_DIR/${id}.out.json"

  cat > "$prompt_file" <<EOF
Audit this single atomic claim as the "pedantic" persona. Claim ID is ${claim_id}.

Claim ${claim_id} (verbatim): "${claim_text}"

Inspect rigorously and emit findings in the required JSON shape. Use claim_audit_count=1.

CRITICAL gap_type rules:
1. If the claim has multiple distinct issues, emit ONE finding per issue (the findings array can have multiple entries).
2. For each finding, choose the MOST SPECIFIC gap_type from the enum. Use "other" only as a true last resort, never to dodge a clear enum match.
3. Numerical constant errors (e.g. missing factor of 2 in a tail bound, wrong base of exponential) MUST be tagged with the dedicated constant-error enum (Hoeffding-constant-wrong, Gaussian-tail-constant-wrong, etc.) — not with regularity nitpicks. Surface the constant error as the highest-severity finding for that claim.
4. Severity 5 means "proof collapses if unaddressed"; severity 1 is cosmetic.
EOF

  if ! codex exec --skip-git-repo-check --sandbox read-only \
        --output-schema "$SCHEMA" \
        --output-last-message "$out_file" \
        < "$prompt_file" > "$OUT_DIR/${id}.stdout.log" 2>&1; then
    echo "  ERROR running codex exec" >&2
    cat "$OUT_DIR/${id}.stdout.log" | tail -10 >&2
    continue
  fi

  # Pick the BEST matching finding: highest-severity one whose gap_type is in
  # expected_gap_types and severity >= min_sev. Fall back to highest-severity
  # finding overall when no match (so we still report what GPT said).
  best=$(jq --argjson exp "$expected_array" --argjson minsev "$min_sev" '
    (.findings // [])
    | (map(select((.gap_type as $g | $exp | index($g)) and .severity >= $minsev))
       | sort_by(-.severity) | .[0])
      // (.findings | sort_by(-.severity) | .[0])
      // null
  ' "$out_file")
  actual_gap=$(echo "$best" | jq -r '.gap_type // "<empty>"')
  actual_sev=$(echo "$best" | jq -r '.severity // 0')
  status=$(   echo "$best" | jq -r '.status // "<empty>"')
  all_gaps=$(jq -r '.findings // [] | map(.gap_type + ":" + (.severity|tostring)) | join(",")' "$out_file")

  in_expected=$(jq -n --argjson exp "$expected_array" --arg g "$actual_gap" '$exp | index($g) != null')
  hit="false"
  if [ "$in_expected" = "true" ] && [ "$actual_sev" -ge "$min_sev" ]; then
    hit="true"
    hits=$((hits+1))
  fi

  jq --arg id "$id" --argjson expected "$expected_array" --arg actual "$actual_gap" \
     --arg status "$status" --argjson sev "${actual_sev:-0}" --argjson minsev "$min_sev" \
     --arg hit "$hit" --arg outpath "$out_file" --arg allgaps "$all_gaps" \
     '.runs += [{canary_id:$id, expected_gap_types:$expected, actual_gap_type:$actual,
                  actual_severity:$sev, expected_severity_min:$minsev,
                  actual_status:$status, all_findings:$allgaps,
                  hit:($hit=="true"), output_file:$outpath}]' \
     "$report" > "$report.tmp" && mv "$report.tmp" "$report"

  printf "  expected=%-60s actual=%-40s sev=%d  %s\n" \
         "$(echo "$expected_array" | jq -r 'join("|")')" "$actual_gap" "$actual_sev" \
         "$([ $hit = true ] && echo HIT || echo MISS)" >&2
done

jq --argjson hits "$hits" --argjson total "$total" \
   --argjson pass "$([ "$hits" -ge 3 ] && echo true || echo false)" \
   '. + {hits:$hits, total:$total, gate_pass_threshold:3, pass:$pass}' \
   "$report" > "$report.tmp" && mv "$report.tmp" "$report"

echo >&2
echo "[canary] $hits / $total hits  (gate: >= 3 to pass)" >&2
echo "[canary] report: $report" >&2

if [ "$hits" -ge 3 ]; then exit 0; else exit 1; fi
