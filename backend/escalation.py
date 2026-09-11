import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# We will use env variables or defaults
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "AC_dummy_sid")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "dummy_token")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "+1234567890")
ESCALATION_TARGET = os.getenv("ESCALATION_TARGET", "+0987654321")


def escalate_alert(alert):
    """Escalate an alert via Twilio SMS. Returns the message body string."""
    print(f"--- ESCALATING ALERT to {ESCALATION_TARGET} ---")
    message_body = (
        f"URGENT: Unacknowledged Railway Safety Alert\n"
        f"Type: {alert.get('layer')}\n"
        f"Details: {alert.get('description')}\n"
        f"Timestamp: {alert.get('detected_at')}\n"
        f"This alert was not acknowledged within the required time window."
    )
    print(message_body)

    # Only actually send if we have a real looking SID
    if (
        TWILIO_ACCOUNT_SID.startswith("AC")
        and len(TWILIO_ACCOUNT_SID) > 10
        and TWILIO_ACCOUNT_SID != "AC_dummy_sid"
    ):
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                body=message_body,
                from_=TWILIO_FROM_NUMBER,
                to=ESCALATION_TARGET,
            )
            print(f"Twilio message sent! SID: {message.sid}")
        except Exception as e:
            print(f"Failed to send Twilio message: {e}")
    else:
        print("Twilio credentials not configured. Skipping actual SMS/WhatsApp dispatch.")

    return message_body
