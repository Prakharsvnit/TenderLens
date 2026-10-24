#!/usr/bin/env bash
# Turn live runs on or off. Past runs stay viewable either way, so "off" keeps the app at $0.
#   scripts/live_runs.sh off [aws-profile]
#   scripts/live_runs.sh on [aws-profile]
#   scripts/live_runs.sh until 2026-11-15 [aws-profile]   # live until that date, then off automatically
set -euo pipefail

ACTION="${1:?usage: scripts/live_runs.sh on|off|until YYYY-MM-DD [aws-profile]}"
if [ "$ACTION" = "until" ]; then
  DATE="${2:?give a date, e.g. 2026-11-15}"
  PROFILE="${3:-tenderlens}"
  [ "${AWS_EXECUTION_ENV:-}" = CloudShell ] || export AWS_PROFILE="$PROFILE"  # CloudShell is already signed in
  aws ssm put-parameter --name /tenderlens/live-runs --type String --value on --overwrite >/dev/null
  aws ssm put-parameter --name /tenderlens/live-until --type String --value "$DATE" --overwrite >/dev/null
  echo "Live runs on until $DATE."
else
  PROFILE="${2:-tenderlens}"
  [ "${AWS_EXECUTION_ENV:-}" = CloudShell ] || export AWS_PROFILE="$PROFILE"  # CloudShell is already signed in
  aws ssm put-parameter --name /tenderlens/live-runs --type String --value "$ACTION" --overwrite >/dev/null
  echo "Live runs $ACTION."
fi
