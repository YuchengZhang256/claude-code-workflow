#!/usr/bin/env bash
# fetch-parallel.sh — fan out fetch.sh across many URLs concurrently.
#
# Each URL is processed by an independent fetch.sh invocation. Results land
# in per-URL files inside an output directory; a manifest.tsv records the
# (idx, exit_code, url, content_file) tuple for each row, in the original
# input order.
#
# This is a parallel divide-and-conquer wrapper: instead of spawning child
# Agents, it forks independent processes that share nothing except the
# filesystem. Suitable for read-only research fanout where each target is
# independent.
#
# Usage:
#   fetch-parallel.sh [-P N] [-o DIR] <url> [url...]
#   fetch-parallel.sh [-P N] [-o DIR] -        # read URLs from stdin
#
# Options:
#   -P N    Max concurrent fetches (default 4). Keep modest: Jina Reader is
#           rate-limited, and curl-impersonate is CPU-heavy.
#   -o DIR  Output directory. Defaults to a fresh mktemp dir.
#   -h      This help.
#
# Output:
#   stderr: progress lines from this script and from each fetch.sh worker
#           (workers' stderr is also captured to <file>.log per URL).
#   stdout: the manifest as TSV (idx<TAB>exit_code<TAB>url<TAB>content_file),
#           sorted by idx. Consume this with awk / cut.
#
# Per-URL exit codes are preserved verbatim from fetch.sh:
#   0  success           — content_file holds cleaned page text
#   2  PDF               — content_file is empty; route to a PDF extractor
#   3  all layers failed — content_file is empty; escalate to chrome-devtools MCP
#
# This wrapper itself exits 0 if it managed to dispatch every URL, regardless
# of individual outcomes. Inspect the manifest to see what failed.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FETCH_SH="$SCRIPT_DIR/fetch.sh"

PARALLEL=4
OUTDIR=""

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//' >&2
}

while getopts ":P:o:h" opt; do
  case "$opt" in
    P) PARALLEL="$OPTARG" ;;
    o) OUTDIR="$OPTARG" ;;
    h) usage; exit 0 ;;
    \?) echo "[fetch-parallel] unknown flag: -$OPTARG" >&2; usage; exit 1 ;;
    :)  echo "[fetch-parallel] -$OPTARG needs an argument" >&2; usage; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

if ! [[ "$PARALLEL" =~ ^[1-9][0-9]*$ ]]; then
  echo "[fetch-parallel] -P must be a positive integer, got: $PARALLEL" >&2
  exit 1
fi

URLS=()
if [ $# -eq 1 ] && [ "$1" = "-" ]; then
  while IFS= read -r line; do
    # Skip blank lines and comments.
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    URLS+=("$line")
  done
elif [ $# -gt 0 ]; then
  URLS=("$@")
else
  echo "[fetch-parallel] no URLs given" >&2
  usage
  exit 1
fi

if [ ${#URLS[@]} -eq 0 ]; then
  echo "[fetch-parallel] URL list is empty" >&2
  exit 1
fi

if [ -z "$OUTDIR" ]; then
  OUTDIR=$(mktemp -d -t web-access-parallel.XXXXXX)
fi
mkdir -p "$OUTDIR"

MANIFEST="$OUTDIR/manifest.tsv"
: > "$MANIFEST"

echo "[fetch-parallel] outdir=$OUTDIR parallel=$PARALLEL urls=${#URLS[@]}" >&2

# One worker = one fetch.sh invocation. Each worker writes to its own
# content file (named by index), so files never collide. The manifest is a
# shared append target; concurrent rows stay coherent because (1) the shell
# opens it in O_APPEND mode, which POSIX guarantees positions each write at
# end-of-file atomically with the write itself, and (2) each manifest row
# is short enough that bash printf produces a single write() syscall, which
# the kernel does not interleave with concurrent writes to the same regular
# file. (PIPE_BUF does not apply here — it covers pipes/FIFOs, not regular
# files.) If you ever extend this to longer rows or non-printf emitters,
# revisit this assumption.
fetch_one() {
  local idx="$1" url="$2"
  local host slug file rc
  host=$(printf '%s' "$url" | sed -E 's|^[a-zA-Z]+://||; s|[/?#].*||; s|:.*||')
  slug=$(printf '%s' "$host" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-60)
  [ -z "$slug" ] && slug="unknown"
  file="$OUTDIR/$(printf '%03d' "$idx")-${slug}.md"
  bash "$FETCH_SH" "$url" > "$file" 2> "${file}.log"
  rc=$?
  printf '%s\t%s\t%s\t%s\n' "$idx" "$rc" "$url" "$file" >> "$MANIFEST"
}

# Bash 3.2-compatible bounded parallelism via a head-of-queue wait. We do
# not have `wait -n`, so we wait for the oldest in-flight pid each time the
# pool is full. Slightly suboptimal (a slow worker blocks the slot until it
# finishes) but correct and dependency-free.
pids=()
for i in "${!URLS[@]}"; do
  fetch_one "$i" "${URLS[$i]}" &
  pids+=($!)
  if [ "${#pids[@]}" -ge "$PARALLEL" ]; then
    wait "${pids[0]}" || true
    pids=("${pids[@]:1}")
  fi
done
wait || true

# Restore input order — workers finish in arbitrary order.
sort -k1,1n -o "$MANIFEST" "$MANIFEST"
cat "$MANIFEST"
