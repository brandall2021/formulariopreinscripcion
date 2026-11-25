import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
from html import escape
from pathlib import Path
from app.infra.config import Settings

LOGO = Path(__file__).with_name("logo-header-dark.png")


def render_email(subject: str, body: str, logo_cid: str) -> str:
    paragraphs = "".join(
        '<p style="margin:0 0 16px;line-height:1.6">' +
        escape(block).replace("\n", "<br>") + "</p>"
        for block in body.strip().split("\n\n") if block.strip()
    )
    return f"""<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#f1f5f9;color:#172033;font:16px Arial,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f1f5f9">
<tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#fff">
<tr><td style="background:#1f3763;border-top:6px solid #e30613;padding:20px 24px;color:#fff">
<img src="cid:{logo_cid}" width="380" alt="Universidad Nacional de Tucumán · Facultad de Ciencias Económicas"
 style="display:block;width:100%;max-width:380px;height:auto;color:#fff">
</td></tr>
<tr><td style="padding:28px 24px;overflow-wrap:anywhere">
<p style="margin:0 0 8px;color:#a9101a;font-size:14px;font-weight:bold">Preinscripciones FACE UNT</p>
<h1 style="margin:0 0 20px;color:#1f3763;font-size:24px;line-height:1.25">{escape(subject)}</h1>
{paragraphs}
</td></tr>
<tr><td style="padding:18px 24px;background:#1f3763;color:#fff;font-size:13px;line-height:1.5">
Facultad de Ciencias Económicas · Universidad Nacional de Tucumán<br>
Av. Independencia 1900 · San Miguel de Tucumán
</td></tr>
</table>
</td></tr></table>
</body></html>"""


class EmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        logo_cid = make_msgid()
        msg.add_alternative(render_email(subject, body, logo_cid[1:-1]), subtype="html")
        msg.get_body(preferencelist=("html",)).add_related(
            LOGO.read_bytes(), maintype="image", subtype="png", cid=logo_cid,
            disposition="inline", filename="face-unt.png")

        smtp_cls = smtplib.SMTP_SSL if self.settings.smtp_ssl else smtplib.SMTP
        with smtp_cls(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
            if self.settings.smtp_tls and not self.settings.smtp_ssl:
                smtp.starttls()
            if self.settings.smtp_user:
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.send_message(msg)
