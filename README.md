# aws-durable-order-workflow

A serverless order approval workflow built with AWS Durable Functions. Demonstrates stateful, long-running workflows on Lambda with human-in-the-loop approval across three execution paths.

## The problem this solves

Traditional order approval systems need polling loops, queues, and a database tracking "pending" states — costing $85–230/month minimum.

This implementation uses a single Lambda function that **pauses mid-execution** waiting for human approval. No servers running while waiting. No cost accumulating.

**Cost comparison:**
| Architecture | Monthly cost |
|---|---|
| Traditional (EC2 + RDS + SQS) | $85–230/month |
| Durable Functions (Lambda + S3) | < $1/month |

## The 3 execution paths

| Path | Amount | Approval | Approver | Behavior |
|---|---|---|---|---|
| Standard | ≤ $1,000 | None | — | Completes instantly |
| Express | $1,001–$2,000 | Required | Supervisor | Pauses, waits for signal |
| Premium | $2,001+ | Required | Manager | Pauses, waits for signal |

## Architecture

API Gateway → my-order-workflow (Lambda) 
├── validate_order 
├── classify_order
├── [send_approval_email + wait_for_callback] ← Express/Premium only 
├── process_payment 
└── arrange_shipping
Approval signal → API Gateway /callback → my-approval-handler → send-durable-execution-callback-success
## Project structure
aws-durable-order-workflow/ 
├── order_workflow.py # Main durable workflow 
├── business_logic.py # Step functions (validate, classify, pay, ship) 
├── approval_handler.py # Callback receiver + SES email sender 
├── template.yaml # SAM infrastructure template 
└── requirements.txt # Python dependencies
## Key implementation notes

**context.step() wrapping** — the SDK expects a callable taking a StepContext:
```python
order = context.step(lambda ctx: business_logic.validate_order(event), "validate_order")
```

**wait_for_callback() pattern** — pass a submitter function that receives the callback_id:
```python
def send_and_wait(callback_id: str, ctx):
    business_logic.send_approval_email(order, callback_id, role)

approval_result = context.wait_for_callback(send_and_wait, "approval")
```

**Callback result deserialization** — result comes back as a string, not a dict:
```python
if isinstance(approval_result, str):
    approval_result = json.loads(approval_result)
approved = approval_result.get('approved', False)
```

## Testing all 3 paths
```bash
# Standard
echo '{"orderId": "STD-001", "amount": 500, "customer": "John Doe"}' > payload_std.json

# Express
echo '{"orderId": "EXP-001", "amount": 1500, "customer": "Jane Smith"}' > payload_exp.json

# Premium
echo '{"orderId": "PRM-001", "amount": 5000, "customer": "Bob Johnson"}' > payload_prm.json

aws lambda invoke \
  --function-name "arn:aws:lambda:us-east-1:<account>:function:my-order-workflow:$LATEST" \
  --invocation-type Event \
  --payload file://payload_std.json \
  --cli-binary-format raw-in-base64-out \
  --region us-east-1 output.json
```

**Check execution status:**
```bash
aws lambda get-durable-execution \
  --durable-execution-arn '<arn-from-invoke-response>' \
  --region us-east-1
```

**Get callback ID for Express/Premium approvals:**
```bash
aws lambda get-durable-execution-history \
  --durable-execution-arn '<arn>' \
  --region us-east-1 2>&1 | cat | grep -A2 'CallbackId'
```

**Send approval signal:**
```bash
aws lambda send-durable-execution-callback-success \
  --callback-id '<callback-id>' \
  --result '{"approved": true}' \
  --region us-east-1
```

## Requirements

- AWS account (Academy or standard)
- Python 3.12+
- aws-durable-execution-sdk-python 1.4.0
- aws-lambda-powertools
- S3 bucket for execution checkpoints
- SES verified email for approval notifications

## Built with

AWS Lambda · AWS Durable Execution SDK · API Gateway · S3 · SES · Python · AWS PowerTools
