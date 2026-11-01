# Deploying to AWS Lambda with SAM

This repository uses AWS SAM to deploy the FastAPI app as a Python 3.12 ZIP
Lambda behind an API Gateway HTTP API. SAM builds the package, uploads it to S3,
and creates the Lambda, API, and execution role from [`template.yaml`](../template.yaml).
This avoids a Lambda container image and manual ECR setup.

## First deployment

### 1. Install the tools and connect your AWS account

Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
and [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html).
Install Docker too if you plan to use `sam build --use-container`.

Sign in with an AWS profile that can create CloudFormation stacks, Lambda,
Lambda Function URLs, API Gateway, IAM roles, and an S3 deployment bucket. If your organization uses
AWS IAM Identity Center, run `aws configure sso`; otherwise configure a profile
using your normal AWS account process. Confirm the selected account with:

```bash
aws sts get-caller-identity
sam --version
```

Do not paste AWS credentials or secret keys into chat.

The previous attempt authenticated successfully but AWS denied
`cloudformation:CreateChangeSet` on `aws-sam-cli-managed-default`. Ask the AWS
administrator to grant the SAM deployment permissions to your IAM principal
before retrying. `aws sts get-caller-identity` confirms who is signed in; it
does not confirm CloudFormation deployment permission.

### 2. Build the Lambda package

From the repository root:

```bash
sam validate --lint
sam build --use-container
```

The container build uses a Lambda-compatible Python environment for packages
with native code. If Docker is unavailable, use Python 3.12 locally and run
`sam build` without `--use-container`.

### 3. Deploy the stack

Run:

```bash
sam deploy --guided
```

Use `readright-api` as the stack name and select `ap-southeast-2` for Sydney.
Allow SAM to create the function's IAM role (`CAPABILITY_IAM`). Enter these
parameters when prompted:

- `SupabaseUrl`
- `SupabaseServiceKey`
- `BackendApiKey`
- `MaiBaseUrl` — accept the default unless the MAI service owner gives you a
  different base URL
- `MaiApiKey` — obtain this from the MAI service owner; keep it private
- `AllowedOrigin` — the frontend origin, such as `https://app.example.com`

If SAM warns that the API has no API Gateway authorizer, confirm the deployment:
authentication is handled by the FastAPI routes (`Bearer` token for the
dashboard and `X-Backend-Key` for trusted backend CRUD). When asked whether to
save the prompted values to `samconfig.toml`, choose **No** so the secret values
are not written to a local config file. At `SAM configuration file
[samconfig.toml]:`, press **Enter** to accept the filename; at the later save
prompt, answer **n**.

When deployment completes, copy `ApiUrl` and check the regular API:

```bash
curl https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com/health
```

The expected response is `{"status":"ok"}`.

The SAM output named `SynchronousApiUrl` is the Lambda Function URL. Use it for
`POST /v1/mai/analyses`; API Gateway HTTP APIs have a 30-second maximum
integration timeout and cannot wait for the MAI service's 120-second SLA. The
Lambda Function URL is protected for this route by `X-Backend-Key` in FastAPI.

The template sets the Lambda timeout to 150 seconds. SAM marks secret
parameters as `NoEcho`. When SAM asks whether to save prompted parameters to
`samconfig.toml`, choose **No** so secrets are not saved there.
