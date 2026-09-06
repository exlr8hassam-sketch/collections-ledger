# 🤖 Free Autonomous Payment Reminder Agent

An intelligent, zero-cost agentic system that scans client payment records daily, determines which invoices require attention, composes polite, personalized reminders containing your exact bank/payment details, and dispatches them automatically.

---

## 🚀 Quick Start (Tested & Ready)

### 1. Run a Dry Run Test
From this directory, run:
```powershell
.\.venv\Scripts\python.exe run_daily.py --dry-run
```
This evaluates all clients in `clients.csv` and displays formatted reminder previews in the console without sending actual messages.

### 2. Process a Specific Client
```powershell
.\.venv\Scripts\python.exe run_daily.py --client CLI-001 --dry-run
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```

### 1. Set Your Bank & Payment Details (in `.env` or `config.py`)
```ini
PAYMENT_BANK_NAME="Your Bank Name"
PAYMENT_ACCOUNT_TITLE="Your Business / Full Name"
PAYMENT_ACCOUNT_NUMBER="1234567890"
PAYMENT_IBAN="PK36SCBL0000001123456701"
PAYMENT_SWIFT="SCBLPKKA"
SUPPORT_CONTACT="+1-555-0199 / billing@mycompany.com"
```

### 2. Enable Free AI Reasoning (Optional, but recommended)
1. Go to [Google AI Studio](https://aistudio.google.com/) and create a free API key (zero cost, generous daily free quota).
2. Add it to `.env`:
```ini
GEMINI_API_KEY="AIzaSy..."
```
*(If no API key is provided, the agent automatically uses smart contextual fallback templates so it never crashes).*

---

## 📡 Free Messaging Channels

You can select your channel by setting `DISPATCHER_MODE` in `.env` or passing `--channel <name>`:

| Mode | Cost | How to Setup |
| :--- | :--- | :--- |
| `whatsapp` *(Recommended)* | **$0.00** | Sends texts directly from your own personal/business WhatsApp. Simply double-click `start-whatsapp-bridge.bat` and scan the QR code once. |
| `simulation` *(Default)* | **$0.00** | Prints formatted preview to console. Zero configuration needed. |
| `email_to_sms` | **$0.00** | For US/Canada phone numbers. Set `SMTP_EMAIL` and `SMTP_PASSWORD` in `.env`. Sends free email to carrier SMS gateway (`@vtext.com`, `@tmomail.net`, `@txt.att.net`). |
| `telegram` | **$0.00** | Create a bot via `@BotFather` on Telegram, set `TELEGRAM_BOT_TOKEN`, and use client's Telegram Chat ID. |
| `twilio` | Trial Credits | Add your `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER`. |

---

## 👥 Managing Clients (`clients.csv`)

Edit `clients.csv` in Excel or any text editor:

| Column | Description | Example |
| :--- | :--- | :--- |
| `client_id` | Unique ID | `CLI-001` |
| `client_name` | Client or company name | `John Doe` |
| `phone` | Recipient phone number | `+15551234567` |
| `carrier` | Carrier for free Email-to-SMS | `verizon`, `att`, `tmobile` |
| `amount_due` | Amount owed | `450.00` |
| `currency` | Currency code | `USD` |
| `invoice_number` | Invoice reference | `INV-2026-081` |
| `due_date` | Payment due date (`YYYY-MM-DD`) | `2026-09-06` |
| `status` | `Pending` or `Paid` | `Pending` |
| `reminders_sent` | Count of reminders sent | `0` (auto-updated by agent) |
| `last_reminded_date`| Timestamp of last text | `2026-09-06` (auto-updated) |

---

## ⏰ Automating Daily Execution on Windows

To run the agent automatically every morning at 9:00 AM:

1. Open PowerShell as Administrator.
2. Run this command to create a scheduled task:
```powershell
$action = New-ScheduledTaskAction -Execute "C:\Users\HASSAM\.gemini\antigravity\scratch\payment-reminder-agent\.venv\Scripts\python.exe" -Argument "run_daily.py" -WorkingDirectory "C:\Users\HASSAM\.gemini\antigravity\scratch\payment-reminder-agent"
$trigger = New-ScheduledTaskTrigger -Daily -At 9am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "DailyPaymentReminderAgent" -Description "Sends automated payment reminders to clients"
```
You can also run it via **GitHub Actions** on a free recurring cron workflow.
