"""Gmail SMTP email sender."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from garmin_digest import constants

logger = logging.getLogger(__name__)


def send(html: str, subject: str):
    sender_display = constants.get("gmail_sender_display", "Garmin Digest")
    sender_address = constants.get("gmail_sender_address", "")
    app_password = constants.get("gmail_app_password", "")
    recipient = constants.get("recipient_email", "")

    from_addr = f"{sender_display} <{sender_address}>"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    logger.info("Sending email to %s", recipient)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_address, app_password)
        server.sendmail(sender_address, recipient, msg.as_string())
    logger.info("Email sent")
