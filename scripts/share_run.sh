#!/usr/bin/env bash
# Make a finished run visible to every signed-in user (for example the demo run, after live runs are off).
#   scripts/share_run.sh RUN_ID [aws-profile]
set -euo pipefail

RUN_ID="${1:?usage: scripts/share_run.sh RUN_ID [aws-profile]}"
PROFILE="${2:-tenderlens}"
TABLE="$(aws cloudformation describe-stacks --stack-name TenderLens --profile "$PROFILE" \
  --query "Stacks[0].Outputs[?OutputKey=='TableName'].OutputValue" --output text)"
aws dynamodb update-item --profile "$PROFILE" --table-name "$TABLE" \
  --key "{\"PK\": {\"S\": \"RUN#$RUN_ID\"}, \"SK\": {\"S\": \"META\"}}" \
  --update-expression "SET shared = :t" --expression-attribute-values '{":t": {"BOOL": true}}'
echo "Run $RUN_ID is now visible to all signed-in users."
