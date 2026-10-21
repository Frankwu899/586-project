#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
bash scripts/start-local.sh "$@"
local_status=$?
if [ "$local_status" -ne 0 ]; then
  read -r -p 'Startup did not complete. Keep the error above for support. Press Return to close.' _
fi
exit "$local_status"
