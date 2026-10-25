#!/usr/bin/env bash
# Make a finished run visible to every signed-in user (for example the demo run, after live runs are off).
#   scripts/share_run.sh RUN_ID [aws-profile]
set -euo pipefail

RUN_ID="${1:?usage: scripts/share_run.sh RUN_ID [aws-profile]}"
PROFILE="${2:-tenderlens}"
[ "${AWS_EXECUTION_ENV:-}" = CloudShell ] || export AWS_PROFILE="$PROFILE"  # CloudShell is already signed in
TABLE="$(aws cloudformation describe-stacks --stack-name TenderLens \
  --query "Stacks[0].Outputs[?OutputKey=='TableName'].OutputValue" --output text)"
aws dynamodb update-item --table-name "$TABLE" \
  --key "{\"PK\": {\"S\": \"RUN#$RUN_ID\"}, \"SK\": {\"S\": \"META\"}}" \
  --update-expression "SET #s = :t" --expression-attribute-names '{"#s": "shared"}' \
  --expression-attribute-values '{":t": {"BOOL": true}}'
echo "Run $RUN_ID is now visible to all signed-in users."
