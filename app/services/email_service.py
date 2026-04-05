import aiosmtplib
from email.message import EmailMessage
from typing import Optional
from app.config import get_settings

async def send_email_with_attachment(
    to_email: str,
    subject: str,
    body_text: str,
    attachment_name: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
):
    """
    Sends an email with an Excel (.xlsx) attachment.
    """
    settings = get_settings()
    
    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_user = settings.SMTP_USER
    smtp_password = settings.SMTP_PASSWORD
    sender_email = settings.SENDER_EMAIL or smtp_user

    if not smtp_user or not smtp_password:
        raise ValueError("SMTP variables (SMTP_USER, SMTP_PASSWORD) are not configured. Email sending is disabled.")

    msg = EmailMessage()
    # Using a professional display name helps avoid Spam filters
    display_name = settings.APP_NAME or "RAHATY"
    msg['From'] = f'"{display_name}" <{sender_email}>'
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.set_content(body_text)

    # Attach a file only when both name and bytes are provided.
    if attachment_name and attachment_bytes is not None:
        msg.add_attachment(
            attachment_bytes,
            maintype='application',
            subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=attachment_name
        )

    import logging
    logger = logging.getLogger(__name__)

    # Primary transport from env, with Gmail-safe fallback between 465 and 587.
    attempts: list[dict] = []
    if smtp_port == 465:
        attempts.append({"port": 465, "use_tls": True, "start_tls": False})
        attempts.append({"port": 587, "use_tls": False, "start_tls": True})
    elif smtp_port == 587:
        attempts.append({"port": 587, "use_tls": False, "start_tls": True})
        attempts.append({"port": 465, "use_tls": True, "start_tls": False})
    else:
        attempts.append({"port": smtp_port, "use_tls": smtp_port == 465, "start_tls": smtp_port != 465})

    last_error: Exception | None = None
    for i, attempt in enumerate(attempts, start=1):
        port = attempt["port"]
        use_tls = attempt["use_tls"]
        start_tls = attempt["start_tls"]
        try:
            logger.info(
                "📧 Attempt %s to send email to %s via %s:%s (use_tls=%s,start_tls=%s)",
                i,
                to_email,
                smtp_host,
                port,
                use_tls,
                start_tls,
            )
            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=port,
                username=smtp_user,
                password=smtp_password,
                use_tls=use_tls,
                start_tls=start_tls,
                timeout=25,
            )
            logger.info("✅ Email sent successfully to %s", to_email)
            return
        except Exception as e:
            last_error = e
            logger.warning("⚠️ SMTP attempt %s failed on %s:%s -> %s", i, smtp_host, port, str(e))

    logger.error("❌ Email sending failed for %s after all SMTP attempts: %s", to_email, str(last_error))
    if last_error:
        raise last_error
