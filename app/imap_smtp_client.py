import imaplib
import smtplib
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import Message
from email.mime.text import MIMEText
from email.utils import parseaddr


def _decode_header(value: str) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _extract_body(message: Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                payload = part.get_payload(decode=True)
                return (payload or b"").decode(part.get_content_charset() or "utf-8", errors="replace")
    payload = message.get_payload(decode=True)
    return (payload or b"").decode(message.get_content_charset() or "utf-8", errors="replace")


def _normalize_reply_subject(subject: str) -> str:
    subject = subject.strip()
    if not subject:
        return "Re: (no subject)"
    lowered = subject.lower()
    while lowered.startswith("re:"):
        subject = subject[3:].lstrip()
        lowered = subject.lower()
    return f"Re: {subject}"


def connect_imap(host: str, port: int, username: str, password: str):
    client = imaplib.IMAP4_SSL(host, port)
    client.login(username, password)
    return client


def list_unseen_uids(client, folder: str):
    client.select(folder)
    status, data = client.search(None, "UNSEEN")
    if status != "OK":
        return []
    return data[0].split()


def fetch_message_by_uid(client, uid: bytes):
    status, data = client.fetch(uid, "(RFC822)")
    if status != "OK" or not data:
        return None
    return message_from_bytes(data[0][1])


def mark_seen(client, uid: bytes):
    client.store(uid, "+FLAGS", "\\Seen")


def parse_imap_message(message: Message):
    from_header = _decode_header(message.get("From", ""))
    reply_to = _decode_header(message.get("Reply-To", "")) or from_header
    subject = _decode_header(message.get("Subject", "")) or "(no subject)"
    message_id = _decode_header(message.get("Message-ID", ""))
    references = _decode_header(message.get("References", ""))

    from_name, from_email = parseaddr(from_header)
    if not from_email:
        return None

    headers = []
    for key, value in message.items():
        headers.append({"name": key, "value": _decode_header(value)})

    return {
        "message_id": message_id,
        "references": references,
        "from_name": from_name or from_email,
        "from_email": from_email,
        "reply_to": parseaddr(reply_to)[1] or from_email,
        "subject": subject,
        "body": _extract_body(message),
        "headers": headers,
    }


def send_smtp_reply(
    to_addr: str,
    subject: str,
    body: str,
    in_reply_to: str,
    references: str,
    cc_addr: str | None,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    smtp_from: str,
):
    mime = MIMEText(body)
    mime["To"] = to_addr
    if cc_addr:
        mime["Cc"] = cc_addr
    mime["Subject"] = _normalize_reply_subject(subject)
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
    if references:
        mime["References"] = references
    mime["From"] = smtp_from

    recipients = [to_addr] + ([cc_addr] if cc_addr else [])

    if smtp_port in (587, 2525):
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_from, recipients, mime.as_string())
    else:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_from, recipients, mime.as_string())


def is_likely_bulk(headers, subject: str, body: str, from_email: str) -> bool:
    subject_lower = (subject or "").lower()
    body_lower = (body or "").lower()
    from_lower = (from_email or "").lower()

    header_map = {header.get("name", "").lower(): header.get("value", "") for header in headers}
    precedence = header_map.get("precedence", "").lower()
    auto_submitted = header_map.get("auto-submitted", "").lower()
    list_unsubscribe = header_map.get("list-unsubscribe", "")
    list_id = header_map.get("list-id", "")
    auto_response = header_map.get("x-auto-response-suppress", "")

    if precedence in {"bulk", "junk", "list"}:
        return True
    if auto_submitted and auto_submitted != "no":
        return True
    if list_unsubscribe or list_id or auto_response:
        return True

    if any(token in from_lower for token in ["no-reply", "noreply", "mailer-daemon", "postmaster"]):
        return True

    subject_tokens = [
        "unsubscribe", "sale", "promotion", "newsletter", "deal",
        "offer", "discount", "webinar", "digest", "trial",
    ]
    if any(token in subject_lower for token in subject_tokens):
        return True

    body_tokens = ["unsubscribe", "view in browser", "manage preferences"]
    if any(token in body_lower for token in body_tokens):
        return True

    return False
