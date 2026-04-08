from aws_lambda_powertools import Logger
from aws_durable_execution_sdk_python import durable_execution, DurableContext
import business_logic
import json

logger = Logger()

@durable_execution
def lambda_handler(event, context: DurableContext):
    logger.info("Starting Order Workflow")

    order = context.step(lambda ctx: business_logic.validate_order(event), "validate_order")

    classification = context.step(lambda ctx: business_logic.classify_order(order), "classify_order")
    logger.info(f"Order classified as: {classification['path']}")

    if classification['requiresApproval']:
        logger.info(f"Suspending workflow for {classification['approverRole']} approval")

        def send_and_wait(callback_id: str, ctx):
            business_logic.send_approval_email(order, callback_id, classification['approverRole'])

        approval_result = context.wait_for_callback(send_and_wait, "approval")

        # Log exact type and value for debugging
        logger.info(f"approval_result type: {type(approval_result)}")
        logger.info(f"approval_result value: {repr(approval_result)}")

        # Handle all possible types
        if isinstance(approval_result, dict):
            approved = approval_result.get('approved', False)
        elif isinstance(approval_result, str):
            try:
                parsed = json.loads(approval_result)
                approved = parsed.get('approved', False)
            except Exception:
                approved = approval_result.lower() == 'true'
        else:
            approved = bool(approval_result)

        if not approved:
            return {
                'orderId': order['orderId'],
                'status': 'REJECTED',
                'reason': 'Denied by approver'
            }

    payment = context.step(lambda ctx: business_logic.process_payment(order), "process_payment")
    shipping = context.step(lambda ctx: business_logic.arrange_shipping(order), "arrange_shipping")

    return {
        'orderId': order['orderId'],
        'status': 'COMPLETED',
        'paymentId': payment['paymentId'],
        'tracking': shipping['trackingNumber']
    }

lambda_handler = lambda_handler
