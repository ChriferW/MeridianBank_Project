#!/usr/bin/env python3
"""
bulk_send_test_emails.py

Sends 500 varied loan application test emails to chrisbankingapp@gmail.com
to demo the LoanIntake Worker's routing logic at scale across all 5 decision paths.

Distribution (100 each):
  100x prefix 100 -> AUTO_APPROVE        (Sarah Mitchell, credit 780, small amounts)
  100x prefix 200 -> MANUAL_REVIEW       (James Chen, credit 700, mid amounts)
  100x prefix 400 -> ESCALATE_HIGH_VALUE (Patricia Williams, >$500K)
  100x prefix 700 -> AUTO_DECLINE        (Robert Hayes, credit 540)
  100x prefix 999 -> BUSINESS_EXCEPTION  (Customer not found)

NOTES ON GMAIL RATE LIMITS:
- Gmail caps SMTP at ~500/day for free accounts; 100/hour bursts will throttle.
- This script uses 1.5s delay (40/min ~ 2400/hour wall, but Gmail batches will block)
- It reconnects automatically every 50 emails to avoid stale-connection drops.
- If Gmail rejects with 421/454/535, the script waits 60s and retries once.
- Expected total runtime: ~12-15 minutes for full 500.

Requires: standard library only.
"""

import smtplib
import ssl
import time
import random
from email.message import EmailMessage

# ---------- Config ----------
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SENDER = "chrisbankingapp@gmail.com"
RECIPIENT = "chrisbankingapp@gmail.com"
APP_PASSWORD = "rlin evks butr pyef"
DELAY_BETWEEN_EMAILS = 1.5
RECONNECT_EVERY_N = 50  # Reconnect SMTP every 50 emails
RETRY_DELAY_ON_ERROR = 60  # If Gmail rejects, wait this long and retry once

# ---------- Test scenarios ----------
SCENARIOS = [
    {"count": 100, "prefix": "100", "amount_range": (3000, 9500), "outcome": "AUTO_APPROVE"},
    {"count": 100, "prefix": "200", "amount_range": (15000, 250000), "outcome": "MANUAL_REVIEW"},
    {"count": 100, "prefix": "400", "amount_range": (550000, 1500000), "outcome": "ESCALATE_HIGH_VALUE"},
    {"count": 100, "prefix": "700", "amount_range": (5000, 50000), "outcome": "AUTO_DECLINE"},
    {"count": 100, "prefix": "999", "amount_range": (5000, 75000), "outcome": "NOT_FOUND"},
]

# ---------- Name pools (50 first × 50 last = 2500 unique combos) ----------
FIRST_NAMES = [
    "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason",
    "Isabella", "Lucas", "Mia", "Logan", "Charlotte", "Aiden", "Amelia",
    "Caleb", "Harper", "Elijah", "Evelyn", "Benjamin", "Victoria", "Alexander",
    "Catherine", "Maximilian", "Genevieve", "Sebastian", "Penelope", "Theodore",
    "Cordelia", "Augustus", "Marcus", "Tasha", "Derek", "Crystal", "Anthony",
    "Brittany", "Jamal", "Latoya", "Devon", "Shanice", "John", "Jane", "Bob",
    "Alice", "Charlie", "Diana", "Edward", "Fiona", "George", "Hannah",
]

LAST_NAMES = [
    "Thompson", "Martinez", "Patel", "Walker", "Nguyen", "Carter", "Garcia",
    "Anderson", "Johnson", "Smith", "Davis", "Brown", "Wilson", "Lee", "Taylor",
    "Clark", "Harris", "Lewis", "Robinson", "Mitchell", "Sterling", "Wellington",
    "Ashford", "Hayes", "Whitmore", "Crawford", "Vance", "Lockhart", "Pemberton",
    "Beaumont", "Reyes", "Williams", "Moore", "Diaz", "Carter", "Robinson",
    "Brown", "Mitchell", "Parker", "Phantom", "Ghost", "Unknown", "Missing",
    "Void", "Null", "Empty", "Absent", "Vacant", "Hidden", "O'Brien",
]

PURPOSES = [
    "Home renovation", "Debt consolidation", "Small business expansion",
    "Medical expenses", "Vehicle purchase", "Education funding",
    "Wedding expenses", "Investment property", "Emergency fund",
    "Equipment purchase", "Home improvement", "Tuition fees",
    "Business equipment", "Solar installation", "Roof replacement",
]


def make_ssn(prefix: str) -> str:
    middle = random.randint(10, 99)
    last = random.randint(1000, 9999)
    return f"{prefix}-{middle}-{last}"


def make_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def build_email(name: str, ssn: str, amount: int, purpose: str, outcome_tag: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg["Subject"] = f"Loan Application - {name}"

    body = f"""Hello,

Please find my loan application details below:

Applicant Name: {name}
SSN: {ssn}
Date of Birth: 01/15/1985
Requested Amount: ${amount:,}
Loan Purpose: {purpose}
Annual Income: $75,000
Employer Name: Acme Corp

Thank you for your consideration.

Regards,
{name}

[demo-tag: {outcome_tag}]
"""
    msg.set_content(body)
    return msg


def connect_smtp():
    """Open a fresh SMTP connection."""
    context = ssl.create_default_context()
    server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30)
    server.login(SENDER, APP_PASSWORD)
    return server


def send_with_retry(server, msg, name, idx, total):
    """Try to send; on transient SMTP errors, reconnect and retry once."""
    try:
        server.send_message(msg)
        return server, True
    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
            smtplib.SMTPResponseException, ssl.SSLError, OSError) as e:
        print(f"[{idx:3d}/{total}] WARN: send failed for {name} ({type(e).__name__}: {e}). "
              f"Waiting {RETRY_DELAY_ON_ERROR}s and reconnecting...")
        try:
            server.quit()
        except Exception:
            pass
        time.sleep(RETRY_DELAY_ON_ERROR)
        try:
            server = connect_smtp()
            server.send_message(msg)
            print(f"[{idx:3d}/{total}] RECOVERED: {name}")
            return server, True
        except Exception as e2:
            print(f"[{idx:3d}/{total}] FAILED after retry: {name} -- {e2}")
            return server, False


def main():
    # Build the full list
    emails_to_send = []
    for scenario in SCENARIOS:
        for _ in range(scenario["count"]):
            name = make_name()
            ssn = make_ssn(scenario["prefix"])
            amount = random.randint(*scenario["amount_range"])
            purpose = random.choice(PURPOSES)
            emails_to_send.append((name, ssn, amount, purpose, scenario["outcome"]))

    random.shuffle(emails_to_send)

    total = len(emails_to_send)
    print(f"Preparing to send {total} test loan application emails")
    print(f"  From: {SENDER}")
    print(f"  To:   {RECIPIENT}")
    print(f"  Delay: {DELAY_BETWEEN_EMAILS}s between emails")
    print(f"  Reconnect: every {RECONNECT_EVERY_N} emails")
    print(f"  Estimated runtime: {(total * DELAY_BETWEEN_EMAILS) / 60:.1f} minutes")
    print()

    server = connect_smtp()
    print(f"Connected to {SMTP_HOST}.\n")

    sent = 0
    failed = 0

    for idx, (name, ssn, amount, purpose, outcome) in enumerate(emails_to_send, 1):
        # Reconnect periodically
        if idx > 1 and (idx - 1) % RECONNECT_EVERY_N == 0:
            try:
                server.quit()
            except Exception:
                pass
            print(f"[{idx:3d}/{total}] Reconnecting SMTP...")
            time.sleep(2)
            server = connect_smtp()

        msg = build_email(name, ssn, amount, purpose, outcome)
        server, ok = send_with_retry(server, msg, name, idx, total)
        if ok:
            sent += 1
            if idx % 10 == 0 or idx <= 5:
                print(f"[{idx:3d}/{total}] Sent: {name:30s} SSN {ssn} ${amount:>10,} -> {outcome}")
        else:
            failed += 1

        time.sleep(DELAY_BETWEEN_EMAILS)

    try:
        server.quit()
    except Exception:
        pass

    print()
    print(f"Done. Sent: {sent}/{total}. Failed: {failed}.")
    print()
    print("Expected queue outcome distribution (approximately):")
    print("  - AUTO_APPROVE       : 100 (Sarah Mitchell, prefix 100)")
    print("  - MANUAL_REVIEW      : 100 (James Chen, prefix 200)")
    print("  - ESCALATE_HIGH_VALUE: 100 (Patricia Williams, prefix 400, all create Action Center tasks)")
    print("  - AUTO_DECLINE       : 100 (Robert Hayes, prefix 700, credit 540)")
    print("  - BUSINESS_EXCEPTION : 100 (Customer Not Found, prefix 999)")
    print()
    print("Next steps:")
    print(f"  1. Verify ~{sent} unread emails in chrisbankingapp@gmail.com inbox")
    print("  2. Run the Loader (LoanIntake.Loader project)")
    print(f"  3. Confirm queue shows ~{sent} New items (Loader takes ~10-15 min for 500)")
    print("  4. Run the Worker (LoanIntake.Worker project, Main.xaml)")
    print()
    print("Note: 100 high-value items will create 100 tasks in Action Center.")


if __name__ == "__main__":
    main()
