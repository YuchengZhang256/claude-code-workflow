#!/usr/bin/env bash
# fetch.sh — layered web fetcher for the web-access skill.
#
# Usage:
#   fetch.sh <url>
#
# Stdout: cleaned page content (markdown preferred, else text).
# Stderr: per-layer progress / debug messages.
# Exit codes:
#   0  success
#   1  usage error
#   2  URL is a PDF — caller should use a dedicated PDF extraction tool
#      (pdftotext, pdfplumber, or an LLM-based extractor)
#   3  all layers failed — caller should escalate to Chrome DevTools MCP
#
# Layers attempted, in order:
#   1. Jina Reader     (https://r.jina.ai/<url>, free headless browser)
#   2. Stealth curl    (Chrome 131 UA + sec-ch-ua + optional curl-impersonate)
#   3. Wayback Machine (archive.org closest snapshot, toolbar stripped)
#
# The script deliberately does not use `set -e`: each layer is expected to
# fail sometimes. `set -u` catches undefined vars; `pipefail` surfaces upstream
# failures in pipes.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="${1:-}"

usage() {
  cat >&2 <<EOF
Usage: $0 <url>
  Fetches <url> through a Jina Reader → stealth curl → Wayback fallback chain.
  If <url> is a PDF, exits 2 (use a dedicated PDF extractor instead).
  If every layer fails, exits 3 (escalate to Chrome DevTools MCP).
EOF
}

if [ -z "$URL" ]; then
  usage
  exit 1
fi

log() { printf '[web-access] %s\n' "$*" >&2; }

# -------- Tunables ------------------------------------------------------------
CHROME_UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
MAX_FILESIZE=10485760    # 10 MB — cap response body size to bound bash memory
MIN_USEFUL_BYTES=150     # shorter than this is almost certainly an error stub
SAMPLE_BYTES=8192        # how much of the response to scan for challenge markers
HTML_MIN_BYTES=100       # html_to_text output shorter than this is treated as failure

# -------- Locate curl-impersonate if available (defeats TLS/JA3 fingerprints) --
IMPERSONATE=""
for cand in /opt/homebrew/bin/curl_chrome* /usr/local/bin/curl_chrome* ; do
  if [ -x "$cand" ]; then
    IMPERSONATE="$cand"
    break
  fi
done

# Detect Brotli support. macOS system curl (as of 8.7) is built without
# Brotli, so requesting `br` results in binary garbage that bash variable
# assignment then truncates at the first NUL byte. Only advertise br if
# the chosen binary actually supports it.
ACCEPT_ENCODING="gzip, deflate"
if [ -n "$IMPERSONATE" ]; then
  # curl-impersonate ships chromium's full codec set.
  ACCEPT_ENCODING="gzip, deflate, br, zstd"
elif curl --version 2>/dev/null | head -1 | grep -qi brotli; then
  ACCEPT_ENCODING="gzip, deflate, br"
fi

# -------- PDF detection: defer to a dedicated extractor ----------------------
# This script enforces "PDFs do not flow through the web fetcher" by exiting 2
# on any URL that either:
#   (a) matches a known PDF extension / path pattern (fast path, no network), or
#   (b) returns Content-Type: application/pdf on a HEAD probe (slow path, one
#       short network round-trip for otherwise-ambiguous URLs).
# Both checks are case-insensitive. If the server rejects HEAD or the URL is
# genuinely ambiguous after both checks, the script falls through to Layer 1;
# in that case Jina Reader may still extract a PDF — this residual gap is
# documented in SKILL.md so the caller can intervene if needed.
is_pdf_url() {
  local u="$1"
  local matched=0

  # Fast path: case-insensitive extension / path pattern match.
  shopt -s nocasematch
  if [[ "$u" =~ \.pdf([?#]|$) ]]; then matched=1
  elif [[ "$u" =~ arxiv\.org/pdf/ ]]; then matched=1
  elif [[ "$u" =~ (bio|med)rxiv\.org/.*\.full\.pdf ]]; then matched=1
  fi
  # Obvious HTML extensions — skip the slow HEAD probe entirely. These are
  # the paths where Jina Reader will correctly handle the content.
  local html_shortcut=0
  if [[ "$u" =~ \.(html?|x?html|php|aspx?|jsp|md|txt)([?#]|$) ]]; then html_shortcut=1; fi
  shopt -u nocasematch
  [ "$matched" = "1" ] && return 0
  [ "$html_shortcut" = "1" ] && return 1

  # Slow path: HEAD probe, requesting only the Content-Type header. Capped
  # at 6 s. `curl -w '%{content_type}'` avoids a three-stage text pipeline.
  local ct
  ct=$(curl -sIL --max-time 6 -o /dev/null -w '%{content_type}' \
        -A "$CHROME_UA" "$u" 2>/dev/null | tr '[:upper:]' '[:lower:]')
  [[ "$ct" == *pdf* ]] && return 0
  return 1
}

if is_pdf_url "$URL"; then
  log "URL looks like a PDF — deferring to a dedicated extractor."
  log "Suggested workflow:"
  log "  curl -sL -o /tmp/doc.pdf '$URL'"
  log "  # then feed /tmp/doc.pdf to pdftotext / pdfplumber / your PDF tool"
  exit 2
fi

# -------- Challenge / empty-page detector -------------------------------------
is_blocked() {
  local text="$1"
  local len=${#text}
  # Truly empty / microscopic responses are always bad.
  [ "$len" -lt "$MIN_USEFUL_BYTES" ] && return 0
  # Sample the first $SAMPLE_BYTES KB via bash parameter expansion (no pipe),
  # then grep on a here-string. This avoids a `set -o pipefail` interaction
  # where `head | grep -q` would propagate head's SIGPIPE exit (141) through
  # the pipeline and make `&& return 0` silently fail on matched challenge
  # pages.
  local head_text="${text:0:SAMPLE_BYTES}"
  if grep -qiE "cf-challenge|just a moment|checking your browser|please enable javascript|captcha|attention required|access denied|403 forbidden|error 1020|cloudflare ray id" <<< "$head_text"; then
    return 0
  fi
  return 1
}

# -------- HTML → text conversion ----------------------------------------------
# Prefers pandoc (if installed). Falls back to the bundled html2text.py.
html_to_text() {
  local input
  input=$(cat)
  local out=""
  if command -v pandoc >/dev/null 2>&1; then
    out=$(printf '%s' "$input" | pandoc -f html -t markdown --wrap=none 2>/dev/null || true)
  fi
  if [ -z "$out" ] || [ "${#out}" -lt "$HTML_MIN_BYTES" ]; then
    out=$(printf '%s' "$input" | python3 "$SCRIPT_DIR/html2text.py" 2>/dev/null || true)
  fi
  if [ -z "$out" ]; then
    out="$input"  # last resort: return raw
  fi
  printf '%s' "$out"
}

# ============================ LAYER 1: Jina Reader ============================
try_jina() {
  log "Layer 1: Jina Reader"
  curl -sL --max-time 45 --max-filesize "$MAX_FILESIZE" \
    -H "Accept: text/markdown" \
    -H "X-Return-Format: markdown" \
    "https://r.jina.ai/$URL" 2>/dev/null
}

# ============================ LAYER 2: Stealth curl ===========================
try_stealth() {
  if [ -n "$IMPERSONATE" ]; then
    log "Layer 2: stealth curl via $(basename "$IMPERSONATE")"
  else
    log "Layer 2: stealth curl (plain curl — install curl-impersonate for TLS spoofing)"
  fi
  local bin="${IMPERSONATE:-curl}"
  "$bin" -sL --compressed --max-time 30 --max-filesize "$MAX_FILESIZE" \
    -A "$CHROME_UA" \
    -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8" \
    -H "Accept-Language: en-US,en;q=0.9" \
    -H "Accept-Encoding: $ACCEPT_ENCODING" \
    -H "sec-ch-ua: \"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not?A_Brand\";v=\"24\"" \
    -H "sec-ch-ua-mobile: ?0" \
    -H "sec-ch-ua-platform: \"macOS\"" \
    -H "Sec-Fetch-Dest: document" \
    -H "Sec-Fetch-Mode: navigate" \
    -H "Sec-Fetch-Site: none" \
    -H "Sec-Fetch-User: ?1" \
    -H "Upgrade-Insecure-Requests: 1" \
    "$URL" 2>/dev/null
}

# ============================ LAYER 3: Wayback Machine ========================
# URL-encode the target URL so characters like & and # do not leak into the
# Wayback availability API's own query string.
urlencode() {
  python3 -c 'import sys, urllib.parse; sys.stdout.write(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}

try_wayback() {
  log "Layer 3: Wayback Machine"
  local api_resp snap raw encoded
  encoded=$(urlencode "$URL")
  api_resp=$(curl -sL --max-time 15 \
    "https://archive.org/wayback/available?url=$encoded" 2>/dev/null)
  if [ -z "$api_resp" ]; then return; fi
  if command -v jq >/dev/null 2>&1; then
    snap=$(printf '%s' "$api_resp" | jq -r '.archived_snapshots.closest.url // empty' 2>/dev/null)
  else
    snap=$(printf '%s' "$api_resp" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
print(d.get("archived_snapshots", {}).get("closest", {}).get("url", ""))
' 2>/dev/null)
  fi
  if [ -z "$snap" ]; then
    log "  → no snapshot available"
    return
  fi
  # /web/TIMESTAMP/URL  →  /web/TIMESTAMPid_/URL  (strips Wayback toolbar)
  raw=$(printf '%s' "$snap" | sed 's|/web/\([0-9]*\)/|/web/\1id_/|')
  curl -sL --max-time 30 --max-filesize "$MAX_FILESIZE" "$raw" 2>/dev/null
}

# ============================ Run the chain ===================================
emit_success() {
  local layer="$1"
  local payload="$2"
  # Layer 1 (Jina) is already markdown; others need HTML→text.
  if [ "$layer" = "jina" ]; then
    printf '%s' "$payload"
  else
    local converted
    converted=$(printf '%s' "$payload" | html_to_text)
    if [ -n "$converted" ] && [ "${#converted}" -gt 100 ]; then
      printf '%s' "$converted"
    else
      printf '%s' "$payload"
    fi
  fi
  log "  ✓ success via $layer (${#payload} raw bytes)"
}

for layer in jina stealth wayback; do
  case "$layer" in
    jina)    OUT=$(try_jina) ;;
    stealth) OUT=$(try_stealth) ;;
    wayback) OUT=$(try_wayback) ;;
  esac

  if [ -z "${OUT:-}" ]; then
    log "  → empty response"
    continue
  fi

  if is_blocked "$OUT"; then
    log "  → blocked / too short (${#OUT} bytes)"
    continue
  fi

  emit_success "$layer" "$OUT"
  exit 0
done

log "All fetch layers failed. Escalate to Chrome DevTools MCP (see SKILL.md Layer 4)."
exit 3
