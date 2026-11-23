#!/usr/bin/env bash
# Fetch an engine from engines.json into engines/<name>/ (shallow). Usage: scripts/fetch_engine.sh <name> [--list]
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "${1:-}" = "--list" ] || [ -z "${1:-}" ]; then
  python3 -c "import json;E=json.load(open('engines.json'))['fetch'];[print(f'{k:32} {v[\"kind\"]:8} {\",\".join(v[\"treatments\"])}') for k,v in E.items()]"; exit 0; fi
repo=$(python3 -c "import json,sys;print(json.load(open('engines.json'))['fetch'][sys.argv[1]]['repo'])" "$1")
start=$(python3 -c "import json,sys;print(json.load(open('engines.json'))['fetch'][sys.argv[1]]['start'])" "$1")
mkdir -p engines
if [ -d "engines/$1/.git" ]; then git -C "engines/$1" pull -q --ff-only; else git clone -q --depth 1 "https://github.com/$repo" "engines/$1"; fi
echo "ready: engines/$1  (read engines/$1/$start first)"
