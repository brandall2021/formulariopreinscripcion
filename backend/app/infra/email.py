import smtplib
from email.message import EmailMessage
from app.infra.config import Settings

class EmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        smtp_cls = smtplib.SMTP_SSL if self.settings.smtp_ssl else smtplib.SMTP
        with smtp_cls(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
            if self.settings.smtp_tls and not self.settings.smtp_ssl:
                smtp.starttls()
            if self.settings.smtp_user:
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.send_message(msg)
