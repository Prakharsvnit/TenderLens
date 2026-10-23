import os

import aws_cdk as cdk

from tenderlens_stack import TenderLensStack

app = cdk.App()
TenderLensStack(
    app,
    "TenderLens",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-west-2"),
    ),
    description="TenderLens: RFP response and compliance agents (serverless, zero idle cost)",
)
app.synth()
