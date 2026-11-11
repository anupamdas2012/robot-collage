#!/usr/bin/env bash
# Fetch owner profile locations for the repos already in .context/raw/repos.json.
# bash 3.2 compatible (no mapfile).
set -uo pipefail
cd "$(dirname "$0")/.."
RAW=.context/raw
: > "$RAW/owners.jsonl"
: > "$RAW/owners.err"

jq -r '.[].owner_login' "$RAW/repos.json" | sort -u | while IFS= read -r o; do
  [ -z "$o" ] && continue
  gh api "users/$o" \
    --jq '{login, type, name, location, company, blog, followers, public_repos, created_at}' \
    >> "$RAW/owners.jsonl" 2>>"$RAW/owners.err" \
    || echo "{\"login\":\"$o\",\"location\":null}" >> "$RAW/owners.jsonl"
done

jq -s '.' "$RAW/owners.jsonl" > "$RAW/owners.json"
echo "[done] owners=$(jq length "$RAW/owners.json") repos=$(jq length "$RAW/repos.json")"
