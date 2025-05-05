# AI_Guardian/src/mail_utils.py

import smtplib
import os
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file in root directory

def send_intruder_alert(image_path, reason):
    sender = os.getenv("EMAIL_SENDER")
    receivers = os.getenv("EMAIL_RECEIVERS").split(",")
    password = os.getenv("EMAIL_PASSWORD")

    msg = EmailMessage()
    msg['Subject'] = f"🚨 AI Guardian Alert: {reason.upper()}"
    msg['From'] = sender
    msg['To'] = ", ".join(receivers)
    msg.set_content(f"""
Alert: Suspicious activity detected.

🔍 Reason: {reason.upper()}
🕒 Time: {os.path.basename(image_path).split('_')[-1].split('.')[0]}

Please find the attached snapshot for visual confirmation.
""")

    # Attach snapshot
    try:
        with open(image_path, 'rb') as f:
            img_data = f.read()
            msg.add_attachment(img_data, maintype='image', subtype='jpeg', filename=os.path.basename(image_path))
    except Exception as e:
        print(f"[ERROR] Failed to attach image: {e}")
        return

    # Send email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg, to_addrs=receivers)
        print(f"[EMAIL SENT] Alert sent to: {', '.join(receivers)}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
