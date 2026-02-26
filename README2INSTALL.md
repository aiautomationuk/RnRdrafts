# cPanel Deployment Guide — ReadAndReply (IMAP/SMTP)

Everything learned from a real deployment on cPanel + CloudLinux + LiteSpeed + Passenger.

---

## Prerequisites

- cPanel hosting with **CloudLinux Python App** selector (LiteSpeed or Apache)
- Python 3.11 available in cPanel
- A MySQL database (cPanel > MySQL Databases)
- An email account with IMAP/SMTP access
- An OpenAI API key and Assistant ID (platform.openai.com/assistants)
- SSH access

---

## Step 1 — Upload the code

SSH in, then clone the repo into your home directory:

```bash
git clone https://github.com/aiautomationuk/RnRsinGoogle.git readandreply
```

This creates `~/readandreply/` with the app files.

---

## Step 2 — Create the MySQL database

In **cPanel > MySQL Databases**:

1. Create database: `USERNAME_readandreply` (cPanel prefixes with your username)
2. Create user: `USERNAME_rnruser` with a strong password
3. Add user to database with **All Privileges**
4. Note the full names — cPanel prepends your username (e.g. `myhost_readandreply`)

---

## Step 3 — Create the `.env` file

```bash
nano ~/readandreply/.env
```

Paste and fill in:

```
DATABASE_URL=mysql://USERNAME_rnruser:PASSWORD@localhost:3306/USERNAME_readandreply
OPENAI_API_KEY=sk-...
OPENAI_ASSISTANT_ID=asst_...
SECRET_KEY=some-random-string-32-chars
ADMIN_SECRET=strong-secret-to-protect-api-endpoints

# IMAP/SMTP account (seeded automatically on first run)
IMAP_HOST=mail.yourdomain.com
IMAP_PORT=993
IMAP_USERNAME=you@yourdomain.com
IMAP_PASSWORD=yourpassword
SMTP_HOST=mail.yourdomain.com
SMTP_PORT=587
SMTP_USERNAME=you@yourdomain.com
SMTP_PASSWORD=yourpassword
SMTP_FROM=you@yourdomain.com

# Optional
POLL_INTERVAL_SECONDS=180
EMERGENCY_CC_EMAIL=
EMERGENCY_CC_LEVEL=important
```

Save: **Ctrl+O**, **Enter**, **Ctrl+X**

> **IMPORTANT:** Make sure the file is saved as UTF-8. If you copy-paste from Word or similar, smart quotes or em-dashes can sneak in and cause a UnicodeDecodeError at startup.

---

## Step 4 — Create the Python App in cPanel

In **cPanel > Setup Python App**:

| Field | Value |
|---|---|
| Python version | 3.11 |
| App root | `readandreply` |
| App URL | `app.yourdomain.com` *(see note below)* |
| Startup file | `passenger_wsgi.py` |
| Entry point | `application` |

Click **Create**, then **Save**.

> **Domain note:** CloudLinux reliably sets up Passenger for the **main domain** automatically. For a **subdomain** (e.g. `app.yourdomain.com`), after creating the app you need to do two extra steps — see Step 5.

---

## Step 5 — Fix subdomain document root (subdomains only)

CloudLinux creates the Python App but doesn't correctly set the subdomain's document root. Fix it manually:

**5a.** In **cPanel > Subdomains**, change the document root for `app.yourdomain.com` to:
```
readandreply/public
```

**5b.** Write the Passenger config to `.htaccess` (CloudLinux leaves it empty for subdomains):

```bash
cat > ~/readandreply/public/.htaccess << 'EOF'
# DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION BEGIN
PassengerAppRoot "/home/USERNAME/readandreply"
PassengerBaseURI "/"
PassengerPython "/home/USERNAME/virtualenv/readandreply/3.11/bin/python"
# DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION END
# DO NOT REMOVE OR MODIFY. CLOUDLINUX ENV VARS CONFIGURATION BEGIN
<IfModule Litespeed>
</IfModule>
# DO NOT REMOVE OR MODIFY. CLOUDLINUX ENV VARS CONFIGURATION END
EOF
```

Replace `USERNAME` with your actual cPanel username.

> **If using the main domain** (e.g. `yourdomain.com`): CloudLinux handles this automatically — skip Step 5.

---

## Step 6 — Fix `passenger_wsgi.py`

**CloudLinux overwrites `passenger_wsgi.py` with an "It works!" template when you create the app.** Always rewrite it immediately after creating the app:

```bash
cat > ~/readandreply/passenger_wsgi.py << 'PYEOF'
import sys
import os

# Passenger starts with system Python, not the virtualenv.
# Manually add virtualenv site-packages to sys.path.
_venv = os.path.join(os.environ.get("HOME", ""), "virtualenv", "readandreply", "3.11")
for _sp in [
    os.path.join(_venv, "lib64", "python3.11", "site-packages"),
    os.path.join(_venv, "lib", "python3.11", "site-packages"),
]:
    if os.path.isdir(_sp) and _sp not in sys.path:
        sys.path.insert(0, _sp)

def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:  # utf-8 required — Passenger defaults to ASCII
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

_load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
os.environ.setdefault("RUN_POLLING", "false")
from app.server import app as application
PYEOF
```

> **Why:** Passenger on CloudLinux invokes the system Python (`/opt/alt/python311`), not the virtualenv Python — even though `PassengerPython` points to the virtualenv. The `sys.path` patch ensures Flask and all packages are found. The `encoding='utf-8'` prevents crashes if `.env` contains any non-ASCII characters.

> **Do NOT use `os.execl` to re-exec into the virtualenv Python** — the `python3` symlink in the virtualenv is broken on CloudLinux and causes a `FileNotFoundError`.

---

## Step 7 — Install Python packages

```bash
~/virtualenv/readandreply/3.11/bin/pip install -r ~/readandreply/requirements.txt
```

> Run this with the virtualenv's own pip, not the system pip.

---

## Step 8 — Verify the app starts

```bash
curl -sk https://app.yourdomain.com/health
# Expected: {"status":"ok"}
```

If you get a 500, check:
```bash
cat ~/readandreply/stderr.log
```

Common errors and fixes:

| Error | Fix |
|---|---|
| `ModuleNotFoundError: flask` | Run pip install (Step 7) |
| `UnicodeDecodeError: ascii` | `.env` has non-ASCII chars — remove them or ensure UTF-8 |
| `FileNotFoundError` in `os.execl` | Remove any `os.execl` re-exec pattern from `passenger_wsgi.py` |
| `No such application` | Passenger `.htaccess` missing or doc root mismatch — redo Step 5 |
| `Database init failed` | Check `DATABASE_URL` credentials |

---

## Step 9 — Set up the cron job

In **cPanel > Cron Jobs**, add:

- **Interval:** `*/3 * * * *`
- **Command:**
```
/home/USERNAME/virtualenv/readandreply/3.11/bin/python3 /home/USERNAME/readandreply/poll_cron.py >> /home/USERNAME/readandreply/poll_cron.log 2>&1
```

Monitor the log:
```bash
tail -f ~/readandreply/poll_cron.log
```

Expected output every 3 minutes:
```
2026-02-26 20:13:04 INFO Polling disabled via RUN_POLLING.
2026-02-26 20:13:04 INFO Polling IMAP for 1 account(s).
```

"Polling disabled via RUN_POLLING" is **normal** — it means the background thread is off (correct), and the cron script is doing the polling instead.

---

## Step 10 — Verify the full stack

```bash
# Health check
curl -sk https://app.yourdomain.com/health

# List IMAP accounts (should show your account with openai_assistant_id populated after first poll)
curl -sk https://app.yourdomain.com/imap/accounts \
  -H "X-Admin-Secret: YOUR_ADMIN_SECRET"
```

---

## Key facts to remember

- **CloudLinux always overwrites `passenger_wsgi.py`** when you create/edit the Python App — always rewrite it immediately after.
- **Passenger uses system Python**, not the virtualenv Python. The `sys.path` patch in `passenger_wsgi.py` is mandatory.
- **Subdomains need a manual doc root fix** — CloudLinux only auto-wires Passenger correctly for main domains.
- **The `.htaccess` in `~/readandreply/public/`** is what activates Passenger. If it's empty or missing, the app returns 404.
- **The cron job calls the virtualenv Python directly** — no `os.execl` needed or wanted.
- **First poll** seeds existing emails as "seen" so the app only replies to new emails going forward.
- **`openai_assistant_id`** in the DB falls back to `OPENAI_ASSISTANT_ID` env var if null.

---

## Updating the app after code changes

```bash
cd ~/readandreply
git pull origin main
touch ~/readandreply/tmp/restart.txt
```

If `passenger_wsgi.py` was in the pull, rewrite it immediately (Step 6) since git pull may have overwritten the server-specific version.
