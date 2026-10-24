#!/usr/bin/env bash
# Create a TenderLens login. Self sign-up is off, so every user is created here.
#   scripts/create_user.sh person@example.com [aws-profile]
# You type the password; it is never stored in this repo. Share it with the person separately.
set -euo pipefail

EMAIL="${1:?usage: scripts/create_user.sh EMAIL [aws-profile]}"
PROFILE="${2:-tenderlens}"
[ "${AWS_EXECUTION_ENV:-}" = CloudShell ] || export AWS_PROFILE="$PROFILE"  # CloudShell is already signed in
POOL="$(aws cloudformation describe-stacks --stack-name TenderLens \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)"

read -r -s -p "Password for $EMAIL (8+ characters with upper, lower, number and symbol): " PASSWORD
echo
aws cognito-idp admin-create-user --user-pool-id "$POOL" --username "$EMAIL" \
  --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true --message-action SUPPRESS >/dev/null
aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username "$EMAIL" \
  --password "$PASSWORD" --permanent
echo "Created $EMAIL."
