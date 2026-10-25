"""One stack, serverless only: nothing in it costs money while idle."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import jsii
from aws_cdk import (
    Aws,
    BundlingOptions,
    CfnOutput,
    Duration,
    ILocalBundling,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_authorizers as authorizers
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_ssm as ssm
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

REPO = Path(__file__).resolve().parents[1]
CODE_EXCLUDES = [
    ".git", ".venv", "**/.venv", "**/node_modules", "web", "infra", "runs", "docs", "evals/reports", "evals/run_eval.py", "scripts",
    "**/__pycache__", "**/.pytest_cache", "**/.ruff_cache", "data/rfps", "backend/tests", "backend/uv.lock",
    "backend/requirements.txt",
]


@jsii.implements(ILocalBundling)
class UvLayerBundling:
    """Installs Linux wheels for the Lambda runtime with uv, so deploys don't need Docker.

    Returns False when uv is missing or a package has no wheel, and CDK falls back to Docker.
    """

    def try_bundle(self, output_dir: str, *args, **kwargs) -> bool:
        if not shutil.which("uv"):
            return False
        target = Path(output_dir) / "python"
        result = subprocess.run([
            "uv", "pip", "install", "-q", "-r", str(REPO / "backend" / "requirements.txt"),
            "--target", str(target), "--python-platform", "x86_64-manylinux_2_28",
            "--python-version", "3.12", "--only-binary", ":all:",
        ])
        if result.returncode != 0:
            shutil.rmtree(target, ignore_errors=True)
        return result.returncode == 0


class TenderLensStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        confirm_timeout = int(self.node.try_get_context("confirmTimeoutSeconds") or 120)
        daily_cap = str(self.node.try_get_context("dailyRunCap") or 5)

        # --- Storage ------------------------------------------------------------------------------
        data = s3.Bucket(
            self, "Data",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[s3.LifecycleRule(prefix="uploads/", expiration=Duration.days(30))],
            cors=[s3.CorsRule(allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET],
                              allowed_origins=["*"], allowed_headers=["*"], max_age=3000)],
        )
        table = dynamodb.Table(
            self, "Table",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        s3deploy.BucketDeployment(
            self, "Library",
            sources=[s3deploy.Source.asset(str(REPO / "data" / "library"))],
            destination_bucket=data, destination_key_prefix="library/",
        )
        s3deploy.BucketDeployment(
            self, "Policy",
            sources=[s3deploy.Source.asset(str(REPO / "data" / "policy"))],
            destination_bucket=data, destination_key_prefix="policy/",
        )

        # --- Guardrail: prompt attacks on RFP text, contextual grounding on claims ----------------
        guardrail = bedrock.CfnGuardrail(
            self, "Guardrail",
            name="tenderlens",
            blocked_input_messaging="Blocked by the TenderLens guardrail.",
            blocked_outputs_messaging="Blocked by the TenderLens guardrail.",
            content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(filters_config=[
                bedrock.CfnGuardrail.ContentFilterConfigProperty(
                    type="PROMPT_ATTACK", input_strength="HIGH", output_strength="NONE"),
            ]),
            contextual_grounding_policy_config=bedrock.CfnGuardrail.ContextualGroundingPolicyConfigProperty(
                filters_config=[
                    bedrock.CfnGuardrail.ContextualGroundingFilterConfigProperty(type="GROUNDING", threshold=0.6),
                    bedrock.CfnGuardrail.ContextualGroundingFilterConfigProperty(type="RELEVANCE", threshold=0.5),
                ]
            ),
        )
        guardrail_version = bedrock.CfnGuardrailVersion(
            self, "GuardrailVersion", guardrail_identifier=guardrail.attr_guardrail_id
        )

        # --- Auth -----------------------------------------------------------------------------------
        users = cognito.UserPool(
            self, "Users",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            feature_plan=cognito.FeaturePlan.LITE,
            account_recovery=cognito.AccountRecovery.NONE,
            removal_policy=RemovalPolicy.DESTROY,
        )
        cognito.CfnUserPoolGroup(
            self, "Viewers", user_pool_id=users.user_pool_id, group_name="viewers",
            description="Can open shared runs but not start or act on runs",
        )
        client = users.add_client(
            "Web", auth_flows=cognito.AuthFlow(user_srp=True), generate_secret=False,
            prevent_user_existence_errors=True,
        )

        # --- Web hosting ------------------------------------------------------------------------------
        web_bucket = s3.Bucket(
            self, "Web", block_public_access=s3.BlockPublicAccess.BLOCK_ALL, enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True,
        )
        distribution = cloudfront.Distribution(
            self, "Cdn",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(web_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            error_responses=[
                cloudfront.ErrorResponse(http_status=403, response_http_status=200, response_page_path="/index.html"),
                cloudfront.ErrorResponse(http_status=404, response_http_status=200, response_page_path="/index.html"),
            ],
        )
        web_origin = f"https://{distribution.distribution_domain_name}"

        # --- Ops parameters (live switch) -----------------------------------------------------------
        live = ssm.StringParameter(self, "LiveRuns", parameter_name="/tenderlens/live-runs", string_value="on")
        live_until = ssm.StringParameter(self, "LiveUntil", parameter_name="/tenderlens/live-until", string_value="none")

        # --- Lambda code and dependencies -------------------------------------------------------------
        deps = lambda_.LayerVersion(
            self, "Deps",
            code=lambda_.Code.from_asset(
                str(REPO / "backend"),
                exclude=[".venv", "tests", "tenderlens", "**/__pycache__", "uv.lock", ".pytest_cache", ".ruff_cache"],
                bundling=BundlingOptions(
                    local=UvLayerBundling(),
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=["bash", "-c",
                             "pip install --no-cache-dir -q -r requirements.txt -t /asset-output/python && "
                             "find /asset-output -type d -name __pycache__ -prune -exec rm -rf {} +"],
                ),
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.X86_64],
            description="TenderLens Python dependencies",
        )
        code = lambda_.Code.from_asset(str(REPO), exclude=CODE_EXCLUDES)
        env = {
            "TL_STORE": "aws",
            "TL_BUCKET": data.bucket_name,
            "TL_TABLE": table.table_name,
            "TL_REGION": Aws.REGION,
            "TL_LLM_MODE": "bedrock",
            "TL_EMBEDDER": self.node.try_get_context("embedder") or "hash",
            "TL_GUARDRAIL_ID": guardrail.attr_guardrail_id,
            "TL_GUARDRAIL_VERSION": guardrail_version.attr_version,
            "TL_LOCAL_DIR": "/tmp/runs",
            "POWERTOOLS_SERVICE_NAME": "tenderlens",
        }
        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[
                "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
                "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-*",
                f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:inference-profile/apac.amazon.nova-*",
            ],
        )
        guardrail_policy = iam.PolicyStatement(
            actions=["bedrock:ApplyGuardrail"], resources=[guardrail.attr_guardrail_arn]
        )

        def function(name: str, handler: str, memory: int, timeout_s: int, ai: bool = True) -> lambda_.Function:
            fn = lambda_.Function(
                self, name,
                runtime=lambda_.Runtime.PYTHON_3_12,
                architecture=lambda_.Architecture.X86_64,
                code=code,
                handler=f"backend.tenderlens.{handler}",
                layers=[deps],
                memory_size=memory,
                timeout=Duration.seconds(timeout_s),
                environment=env,
                tracing=lambda_.Tracing.ACTIVE,
                log_group=logs.LogGroup(self, f"{name}Logs", retention=logs.RetentionDays.TWO_WEEKS,
                                        removal_policy=RemovalPolicy.DESTROY),
            )
            data.grant_read_write(fn)
            table.grant_read_write_data(fn)
            if ai:
                fn.add_to_role_policy(bedrock_policy)
                fn.add_to_role_policy(guardrail_policy)
            return fn

        h = "pipeline.handlers"
        parse_fn = function("ParseStep", f"{h}.parse", 1024, 300)
        extract_fn = function("ExtractStep", f"{h}.extract", 1024, 900)
        plan_fn = function("PlanAssessStep", f"{h}.plan_assess", 512, 120, ai=False)
        assess_fn = function("AssessStep", f"{h}.assess", 1024, 900)
        merge_fn = function("MergeAssessStep", f"{h}.merge_assess", 512, 120, ai=False)
        draft_fn = function("DraftStep", f"{h}.draft", 1024, 900)
        verify_fn = function("VerifyStep", f"{h}.verify", 1024, 900)
        decide_fn = function("DecideStep", f"{h}.decide", 1024, 600)
        publish_fn = function("PublishStep", f"{h}.publish", 1024, 300, ai=False)
        checkpoint_fn = function("CheckpointStep", f"{h}.checkpoint", 256, 30, ai=False)
        failed_fn = function("MarkFailedStep", f"{h}.mark_failed", 256, 30, ai=False)

        # --- Workflow: the deterministic supervisor -------------------------------------------------
        def invoke(name: str, fn: lambda_.Function, payload: sfn.TaskInput | None = None) -> tasks.LambdaInvoke:
            return tasks.LambdaInvoke(
                self, name, lambda_function=fn, payload=payload, payload_response_only=True,
                retry_on_service_exceptions=True,
            )

        run_only = sfn.TaskInput.from_object({"run_id": sfn.JsonPath.string_at("$.run_id")})
        failed = invoke("MarkFailed", failed_fn).next(sfn.Fail(self, "RunFailed"))

        def guarded(task: sfn.TaskStateBase) -> sfn.TaskStateBase:
            task.add_retry(errors=["ThrottlingException", "Lambda.TooManyRequestsException"],
                           interval=Duration.seconds(20), max_attempts=3, backoff_rate=2)
            task.add_catch(failed, errors=["States.ALL"], result_path="$.error")
            return task

        parse_t = guarded(invoke("Parse", parse_fn))
        extract_t = guarded(invoke("Extract", extract_fn))
        plan_t = guarded(invoke("PlanAssess", plan_fn))
        confirm_t = tasks.LambdaInvoke(
            self, "ConfirmRequirements", lambda_function=checkpoint_fn,
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            payload=sfn.TaskInput.from_object({"run_id": sfn.JsonPath.string_at("$.run_id"), "kind": "confirm",
                                               "token": sfn.JsonPath.task_token}),
            result_path=sfn.JsonPath.DISCARD,
            task_timeout=sfn.Timeout.duration(Duration.seconds(confirm_timeout)),
        )
        confirm_t.add_catch(plan_t, errors=["States.Timeout"], result_path=sfn.JsonPath.DISCARD)
        assess_map = sfn.Map(self, "Assess", items_path="$.batches", max_concurrency=2, result_path=sfn.JsonPath.DISCARD)
        assess_map.item_processor(invoke("AssessBatch", assess_fn))
        assess_map.add_catch(failed, errors=["States.ALL"], result_path="$.error")
        merge_t = guarded(invoke("MergeAssess", merge_fn, run_only))
        draft_t = guarded(invoke("Draft", draft_fn))
        verify_t = guarded(invoke("Verify", verify_fn))
        decide_t = guarded(invoke("Decide", decide_fn))
        publish_t = guarded(invoke("Publish", publish_fn, run_only))
        approve_t = tasks.LambdaInvoke(
            self, "ApproveDecision", lambda_function=checkpoint_fn,
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            payload=sfn.TaskInput.from_object({"run_id": sfn.JsonPath.string_at("$.run_id"), "kind": "approve",
                                               "token": sfn.JsonPath.task_token}),
            result_path=sfn.JsonPath.DISCARD,
            task_timeout=sfn.Timeout.duration(Duration.days(7)),
        )
        approve_t.add_catch(publish_t, errors=["States.Timeout"], result_path=sfn.JsonPath.DISCARD)
        rewrite = sfn.Choice(self, "UnsupportedClaims").when(
            sfn.Condition.boolean_equals("$.rewrite", True), draft_t
        ).otherwise(decide_t)
        decide_t.next(approve_t).next(publish_t)
        definition = (
            parse_t.next(extract_t).next(confirm_t).next(plan_t).next(assess_map).next(merge_t)
            .next(draft_t).next(verify_t).next(rewrite)
        )
        workflow = sfn.StateMachine(
            self, "Workflow",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            state_machine_type=sfn.StateMachineType.STANDARD,
            timeout=Duration.days(8),
            tracing_enabled=True,
        )

        # --- API ------------------------------------------------------------------------------------
        api_fn = function("ApiHandler", "api.handler.handler", 512, 29, ai=False)
        api_fn.add_environment("TL_STATE_MACHINE_ARN", workflow.state_machine_arn)
        api_fn.add_environment("TL_WEB_ORIGIN", web_origin)
        api_fn.add_environment("TL_DAILY_RUN_CAP", daily_cap)
        workflow.grant_start_execution(api_fn)
        workflow.grant_task_response(api_fn)
        live.grant_read(api_fn)
        live_until.grant_read(api_fn)
        http_api = apigw.HttpApi(
            self, "Api",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=[web_origin, "http://localhost:5173"],
                allow_headers=["Authorization", "Content-Type"],
                allow_methods=[apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.OPTIONS],
                max_age=Duration.hours(1),
            ),
        )
        jwt = authorizers.HttpJwtAuthorizer(
            "Cognito", f"https://cognito-idp.{Aws.REGION}.amazonaws.com/{users.user_pool_id}",
            jwt_audience=[client.user_pool_client_id],
        )
        api_integration = integrations.HttpLambdaIntegration("ApiIntegration", api_fn)
        http_api.add_routes(
            path="/{proxy+}", methods=[apigw.HttpMethod.GET, apigw.HttpMethod.POST],
            integration=api_integration, authorizer=jwt,
        )
        # The public demo: read-only GETs of shared runs, no sign-in. The handler serves only shared runs here.
        http_api.add_routes(path="/public/{proxy+}", methods=[apigw.HttpMethod.GET], integration=api_integration)

        web_dist = REPO / "web" / "dist"
        sources = [s3deploy.Source.json_data("config.json", {
            "apiUrl": http_api.api_endpoint,
            "region": Aws.REGION,
            "userPoolId": users.user_pool_id,
            "userPoolClientId": client.user_pool_client_id,
        })]
        if web_dist.exists():
            sources.insert(0, s3deploy.Source.asset(str(web_dist), exclude=["config.json"]))
        s3deploy.BucketDeployment(
            self, "Site", sources=sources, destination_bucket=web_bucket,
            distribution=distribution, distribution_paths=["/*"],
        )

        # --- Observability ------------------------------------------------------------------------------
        failed_runs = workflow.metric_failed(period=Duration.hours(1))
        cloudwatch.Alarm(self, "FailedRuns", metric=failed_runs, threshold=1, evaluation_periods=1,
                         alarm_description="A TenderLens run failed")
        dashboard = cloudwatch.Dashboard(self, "Dashboard", dashboard_name="TenderLens")

        def kpi(name: str, stat: str = "Average") -> cloudwatch.Metric:
            return cloudwatch.Metric(namespace="TenderLens", metric_name=name, statistic=stat,
                                     dimensions_map={"service": "pipeline"}, period=Duration.days(1))

        dashboard.add_widgets(
            cloudwatch.GraphWidget(title="Time to first draft (s)", left=[kpi("TimeToFirstDraft")]),
            cloudwatch.GraphWidget(title="Coverage and evidence-backed rate (%)",
                                   left=[kpi("RequirementCoverage"), kpi("EvidenceBackedClaimRate")]),
            cloudwatch.GraphWidget(title="Cost per run (USD)", left=[kpi("RunCostUSD", "Sum")]),
            cloudwatch.GraphWidget(title="Runs", left=[workflow.metric_succeeded(), failed_runs]),
        )

        for key, value in {
            "WebUrl": web_origin, "ApiUrl": http_api.api_endpoint, "UserPoolId": users.user_pool_id,
            "UserPoolClientId": client.user_pool_client_id, "DataBucket": data.bucket_name,
            "TableName": table.table_name, "StateMachineArn": workflow.state_machine_arn,
            "GuardrailId": guardrail.attr_guardrail_id,
        }.items():
            CfnOutput(self, key, value=value)
