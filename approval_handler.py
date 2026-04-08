# approval_handler.py
# Phase 4 – Steps 4.2 & 4.3 combined
# Handles incoming approval callbacks AND sends approval emails with the callback URL

import json
import os
import boto3
from aws_lambda_powertools import logger
from aws_lambda_powertools.utilities.durable_execution import DurableExecutionClient

logger = Logger()
client = boto3.client('lambda')

def lambda_handler(event, context):
    # API Gateway passes data in the 'body'
    body = json.loads(event.get('body', '{}'))
    
    # These are the critical pieces to resume the workflow
    callback_id = body.get('callback_id')
    execution_arn = body.get('execution_arn')
    approved = body.get('approved', False)

    if not callback_id or not execution_arn:
        return {"statusCode": 400, "body": "Missing callback_id or execution_arn"}

    logger.info(f"Sending approval signal to {execution_arn}")

    # SIGNAL THE WORKFLOW TO RESUME
    client.send_external_event(
        ExecutionArn=execution_arn,
        EventName=callback_id,
        Payload=json.dumps({"approved": approved})
    )

    return {
        "statusCode": 200, 
        "body": json.dumps({"message": f"Signal sent! Approved: {approved}"})
    }

s3_client    = boto3.client('s3')
ses_client   = boto3.client('ses', region_name='us-east-1')
durable      = DurableExecutionClient()

# ── 4.2  CALLBACK RECEIVER ────────────────────────────────────────────────────
# API Gateway calls this when the approver clicks Approve or Reject in the email.
# It forwards the decision to the suspended workflow so it can resume.

def lambda_handler(event, context):
    body        = json.loads(event['body'])
    callback_id = body['callbackId']
    approved    = body['approved']
    reason      = body.get('reason', '')

    # Resume the suspended durable workflow
    durable.send_callback(
        callback_id=callback_id,
        result={'approved': approved, 'reason': reason}
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Approval recorded successfully'})
    }


# ── 4.3  EMAIL SENDER ─────────────────────────────────────────────────────────
# The durable workflow calls this BEFORE suspending on wait_for_callback().
# It builds Approve / Reject links that embed the callback ID and emails them.

def get_approver_email(approver_role):
    """Map a role name to the actual approver email address."""
    role_map = {
        'manager':    'edgar.cantu77@hotmail.com',
        'supervisor': 'edgar.cantu77@hotmail.com',   # update if different
    }
    return role_map.get(approver_role, 'edgar.cantu77@hotmail.com')


def send_approval_email(order, callback_id, approver_role):
    """
    Construct clickable Approve / Reject URLs and send them via SES.
    API_GATEWAY_URL is set as a Lambda environment variable once your
    API Gateway endpoint is live.
    """
    api_url     = os.environ.get('API_GATEWAY_URL', 'https://YOUR_API_GW_URL/prod/callback')
    approve_url = f"{api_url}?callbackId={callback_id}&approved=true"
    reject_url  = f"{api_url}?callbackId={callback_id}&approved=false"
    to_email    = get_approver_email(approver_role)

    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; padding: 24px;">
      <h2 style="color: #1E4D8C;">Order Approval Required</h2>
      <p>Order <strong>{order['orderId']}</strong> for
         <strong>${order['amount']:,.2f}</strong> requires your approval.</p>
      <table>
        <tr><td><strong>Customer:</strong></td><td>{order.get('customer', 'N/A')}</td></tr>
        <tr><td><strong>Amount:</strong></td>  <td>${order['amount']:,.2f}</td></tr>
        <tr><td><strong>Path:</strong></td>    <td>{approver_role.upper()} approval</td></tr>
      </table>
      <br>
      <a href="{approve_url}"
         style="background:#1E4D8C;color:white;padding:12px 24px;
                text-decoration:none;border-radius:4px;margin-right:12px;">
        ✅ Approve
      </a>
      <a href="{reject_url}"
         style="background:#993C1D;color:white;padding:12px 24px;
                text-decoration:none;border-radius:4px;">
        ❌ Reject
      </a>
      <br><br>
      <p style="color:#888;font-size:12px;">
        This link expires in {'60' if approver_role == 'manager' else '30'} minutes.
      </p>
    </body></html>
    """

    ses_client.send_email(
        Source='edgar.cantu77@hotmail.com',
        Destination={'ToAddresses': [to_email]},
        Message={
            'Subject': {
                'Data': f"[Action Required] Order {order['orderId']} – {approver_role.capitalize()} Approval"
            },
            'Body': {
                'Html': {'Data': html_body},
                'Text': {'Data': (
                    f"Order {order['orderId']} (${order['amount']:,.2f}) needs your approval.\n\n"
                    f"APPROVE: {approve_url}\n\n"
                    f"REJECT:  {reject_url}"
                )}
            }
        }
    )
    print(f"Approval email sent to {to_email} for order {order['orderId']}")