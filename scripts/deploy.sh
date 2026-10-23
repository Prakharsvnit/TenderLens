#!/usr/bin/env bash
# Deploy TenderLens to an AWS account.
#   scripts/deploy.sh [aws-profile]        default profile: tenderlens, region: us-west-2
# Needs: AWS CLI (profile configured), uv, Node 20+, pnpm, Docker running.
set -euo pipefail

PROFILE="${1:-tenderlens}"
REGION="${AWS_REGION:-us-west-2}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export AWS_PROFILE="$PROFILE" CDK_DEFAULT_REGION="$REGION" JSII_SILENCE_WARNING_DEPRECATED_NODE_VERSION=1
CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
export CDK_DEFAULT_ACCOUNT
echo "Deploying to account $CDK_DEFAULT_ACCOUNT in $REGION with profile $PROFILE"

echo "1/5 Lambda dependencies"
(cd "$ROOT/backend" && uv export --no-dev --no-hashes --no-emit-project --no-header -q -o requirements.txt)

echo "2/5 Evidence index with Titan Text Embeddings V2"
EMBEDDER=bedrock
if ! (cd "$ROOT/backend" && TL_AWS_PROFILE="$PROFILE" TL_REGION="$REGION" \
      uv run python -m tenderlens.retrieval.build --embedder bedrock); then
  echo "   Titan embeddings unavailable; falling back to the offline hashing embedder"
  EMBEDDER=hash
  (cd "$ROOT/backend" && uv run python -m tenderlens.retrieval.build --embedder hash)
fi

echo "3/5 Web app"
(cd "$ROOT/web" && pnpm install --frozen-lockfile && pnpm build)

echo "4/5 CDK bootstrap (no-op after the first time)"
(cd "$ROOT/infra" && npx --yes aws-cdk@2 bootstrap "aws://$CDK_DEFAULT_ACCOUNT/$REGION")

echo "5/5 Deploy"
(cd "$ROOT/infra" && npx --yes aws-cdk@2 deploy --require-approval never -c "embedder=$EMBEDDER" \
  --outputs-file cdk-outputs.json)

echo
echo "Done. Web app URL:"
python -c "import json;print(json.load(open('$ROOT/infra/cdk-outputs.json'))['TenderLens']['WebUrl'])"
echo "Create a login with: scripts/create_user.sh you@example.com $PROFILE"
