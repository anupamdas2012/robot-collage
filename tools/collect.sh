#!/usr/bin/env bash
# Discover robotics repos across many GitHub topics/keywords, dedupe, keep top-N by stars,
# then look up each owner's location/country. Outputs .context/raw/repos.json and owners.json
set -uo pipefail
cd "$(dirname "$0")/.."
RAW=.context/raw
mkdir -p "$RAW"
: > "$RAW/items.jsonl"

CAP=300          # max repos to keep (top by stars after dedupe)
PACE=2.5         # seconds between search calls (search limit = 30/min)

# Query set: topics + keyword searches covering the robotics landscape.
QUERIES=(
  "topic:robotics"
  "topic:robot"
  "topic:ros"
  "topic:ros2"
  "topic:robot-operating-system"
  "topic:slam"
  "topic:visual-slam"
  "topic:lidar"
  "topic:drone"
  "topic:uav"
  "topic:quadcopter"
  "topic:autonomous-driving"
  "topic:self-driving-car"
  "topic:autonomous-vehicles"
  "topic:humanoid-robot"
  "topic:humanoid"
  "topic:quadruped"
  "topic:legged-robots"
  "topic:robot-arm"
  "topic:manipulation"
  "topic:motion-planning"
  "topic:path-planning"
  "topic:robotics-simulation"
  "topic:mobile-robots"
  "topic:robotic"
  "topic:robotics-control"
  "topic:ros-noetic"
  "topic:gazebo"
  "topic:robot-learning"
  "topic:embodied-ai"
  "robotics in:name,description stars:>150"
  "robot arm in:name,description stars:>150"
  "reinforcement learning robot in:name,description stars:>150"
)

n=0
for q in "${QUERIES[@]}"; do
  for page in 1 2; do
    echo "[search] ($((++n))) page $page :: $q" >&2
    gh api -X GET search/repositories \
      -f q="$q sort:stars" -f sort=stars -f order=desc \
      -f per_page=100 -f page="$page" \
      --jq '.items[] | {full_name, html_url, name,
             owner_login: .owner.login, owner_type: .owner.type, owner_url: .owner.html_url,
             description, stars: .stargazers_count, forks: .forks_count,
             open_issues: .open_issues_count, language, topics,
             created_at, pushed_at, updated_at, homepage,
             license: (.license.spdx_id // null), archived}' \
      >> "$RAW/items.jsonl" 2>>"$RAW/search.err" || echo "  (query failed)" >&2
    sleep "$PACE"
  done
done

echo "[dedupe] collected $(wc -l < "$RAW/items.jsonl") rows" >&2
# Dedupe by full_name, drop forks-of-noise by requiring stars, sort by stars desc, cap.
jq -s "map(select(.stars != null and .archived != true))
       | unique_by(.full_name)
       | sort_by(-.stars)
       | .[0:$CAP]" "$RAW/items.jsonl" > "$RAW/repos.json"
echo "[repos] kept $(jq length "$RAW/repos.json")" >&2

# Unique owners -> fetch location. (bash 3.2 compatible: while-read, not mapfile)
: > "$RAW/owners.jsonl"
jq -r '.[].owner_login' "$RAW/repos.json" | sort -u | while IFS= read -r o; do
  [ -z "$o" ] && continue
  gh api "users/$o" \
    --jq '{login, type, name, location, company, blog, followers, public_repos, created_at}' \
    >> "$RAW/owners.jsonl" 2>>"$RAW/owners.err" \
    || echo "{\"login\":\"$o\",\"location\":null}" >> "$RAW/owners.jsonl"
done
jq -s '.' "$RAW/owners.jsonl" > "$RAW/owners.json"
echo "[done] owners=$(jq length "$RAW/owners.json") repos=$(jq length "$RAW/repos.json")" >&2
