# business_logic.py

def validate_order(event):
    """Check inventory, payment method, and shipping address."""
    return {
        'orderId': event['orderId'],
        'amount': event['amount'],
        'customer': event['customer'],
        'valid': True
    }

def classify_order(order):
    """Classify order into Standard, Express, or Premium path."""
    amount = order['amount']
    if amount <= 1000:
        return {'path': 'STANDARD', 'requiresApproval': False}
    elif amount <= 2000:
        return {'path': 'EXPRESS', 'requiresApproval': True, 'approverRole': 'supervisor'}
    else:
        return {'path': 'PREMIUM', 'requiresApproval': True, 'approverRole': 'manager'}

def send_approval_email(order, callback_id, approver_role):
    """Send approval request email to the appropriate approver."""
    print(f"Sending email to {approver_role} for order {order['orderId']}")
    print(f"Callback ID: {callback_id}")
    return {'status': 'EMAIL_SENT'}

def process_payment(order):
    """Call payment gateway to charge the customer."""
    return {'paymentId': 'PAY-' + order['orderId'], 'status': 'CHARGED'}

def arrange_shipping(order):
    """Call courier API to arrange shipment."""
    return {'trackingNumber': 'TRK-' + order['orderId'], 'eta': '2 days'}