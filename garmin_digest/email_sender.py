"""Gmail SMTP email sender."""

import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from garmin_digest.constants import (
    GMAIL_APP_PASSWORD,
    GMAIL_SENDER_ADDRESS,
    GMAIL_SENDER_DISPLAY,
    RECIPIENT_EMAIL,
)

logger = logging.getLogger(__name__)


def send(html: str, subject: str):
    from_addr = f"{GMAIL_SENDER_DISPLAY} <{GMAIL_SENDER_ADDRESS}>"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    logger.info("Sending email to %s", RECIPIENT_EMAIL)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_SENDER_ADDRESS, RECIPIENT_EMAIL, msg.as_string())
    logger.info("Email sent")
