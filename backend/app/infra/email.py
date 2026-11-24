import smtplib
from email.message import EmailMessage
from app.infra.config import Settings

class EmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings
    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = "preinscripcion@face.unt.edu.ar"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as smtp:
            smtp.send_message(msg)
