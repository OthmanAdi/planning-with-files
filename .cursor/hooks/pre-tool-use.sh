#!/bin/bash
# planning-with-files: Pre-tool-use hook for Cursor
# Cursor preToolUse is a permission hook. Plan context is injected by sessionStart.
# Always allow tools; this hook never blocks them.

echo '{"permission":"allow"}'
exit 0
