#!/bin/bash

set -euo pipefail

missing=0

require_file() {
  local path="$1"
  if [ ! -f "$path" ]; then
    echo "Missing: $path"
    missing=1
  fi
}

require_file ".continue/prompts/planning-with-files.prompt"
require_file ".continue/skills/planning-with-files/SKILL.md"
require_file ".continue/skills/planning-with-files/examples.md"
require_file ".continue/skills/planning-with-files/reference.md"
require_file ".continue/skills/planning-with-files/scripts/init-session.sh"
require_file ".continue/skills/planning-with-files/scripts/init-session.ps1"
require_file ".continue/skills/planning-with-files/scripts/check-complete.sh"
require_file ".continue/skills/planning-with-files/scripts/check-complete.ps1"
require_file ".continue/skills/planning-with-files/scripts/session-catchup.py"

if [ "$missing" -ne 0 ]; then
  exit 1
fi

case ".continue/prompts/planning-with-files.prompt" in
  *.prompt) ;;
  *) echo "Prompt file must end with .prompt"; exit 1 ;;
esac

echo "Continue integration files look OK."
