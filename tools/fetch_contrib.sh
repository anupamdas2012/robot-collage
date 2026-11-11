#!/usr/bin/env bash
# Fetch an approximate contributor count per repo (proxy for "project size / contributions").
# Uses the Link header trick: contributors?per_page=1 -> rel="last" page number == count.
# bash 3.2 compatible.
set -uo pipefail
cd "$(dirname "$0")/.."
RAW=.context/raw
: > "$RAW/contributors.jsonl"
: > "$RAW/contributors.err"

jq -r '.[].full_name' "$RAW/repos.json" | while IFS= read -r fn; do
  [ -z "$fn" ] && continue
  hdr=$(gh api -i "repos/$fn/contributors?per_page=1&anon=true" 2>>"$RAW/contributors.err" | tr -d '\r')
  last=$(printf '%s\n' "$hdr" | grep -i '^link:' | grep -oE 'page=[0-9]+>; rel="last"' | grep -oE '[0-9]+' | head -1)
  if [ -z "$last" ]; then
    # No pagination -> 0 or 1 contributor returned; fall back to array length.
    last=$(gh api "repos/$fn/contributors?per_page=100&anon=true" --jq 'length' 2>>"$RAW/contributors.err" || echo 0)
  fi
  printf '{"full_name":"%s","contributors":%s}\n' "$fn" "${last:-0}" >> "$RAW/contributors.jsonl"
done

jq -s '.' "$RAW/contributors.jsonl" > "$RAW/contributors.json"
echo "[done] contributors for $(jq length "$RAW/contributors.json") repos"
