import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# -----------------------------------------------------------------------------
# 1. Your Receiving Account Details (Edit these to match your payment details)
# -----------------------------------------------------------------------------
PAYMENT_DETAILS = {
    "bank_name": os.getenv("PAYMENT_BANK_NAME", "Telenor Microfinance Bank (Easypaisa)"),
    "account_title": os.getenv("PAYMENT_ACCOUNT_TITLE", "HASSAM UL HAQ"),
    "account_number": os.getenv("PAYMENT_ACCOUNT_NUMBER", "03329755091"),
    "iban": os.getenv("PAYMENT_IBAN", "PK50TMFB0000000097772042"),
    "routing_or_swift": os.getenv("PAYMENT_SWIFT", ""),
    "payment_link": os.getenv("PAYMENT_LINK", ""),
    "support_contact": os.getenv("SUPPORT_CONTACT", "+92 332 9755091")
}

# -----------------------------------------------------------------------------
# 2. Agent & Policy Settings
# -----------------------------------------------------------------------------
REMINDER_POLICY = {
    # Days before due date to start sending polite reminders (Prior Days)
    "advance_notice_days": int(os.getenv("ADVANCE_NOTICE_DAYS", "3")),
    
    # Gap in days between reminders if payment is delayed / overdue
    "overdue_gap_days": int(os.getenv("OVERDUE_GAP_DAYS", os.getenv("REMINDER_COOLDOWN_DAYS", "2"))),
    
    # Cooldown days (backward compatible with cooldown_days)
    "cooldown_days": int(os.getenv("OVERDUE_GAP_DAYS", os.getenv("REMINDER_COOLDOWN_DAYS", "2"))),
    
    # Maximum total reminders to send to a single client before flagging for manual review
    "max_reminders": int(os.getenv("MAX_REMINDERS", "5")),
    
    # Automatically roll client to next month's invoice upon payment confirmation
    "auto_roll_monthly": os.getenv("AUTO_ROLL_MONTHLY", "false").lower() == "true",

    # AI Model to use for composing personalized messages
    "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
}

# -----------------------------------------------------------------------------
# 3. Messaging Dispatcher Configuration
# -----------------------------------------------------------------------------
# Options: "whatsapp" (default), "simulation", "email_to_sms", "telegram", "twilio"
DISPATCHER_MODE = os.getenv("DISPATCHER_MODE", "whatsapp").lower()

# Free Gemini API Key (get from https://aistudio.google.com/)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Telegram Bot settings (100% free if using Telegram channel)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Twilio settings (if using Twilio trial / paid SMS)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

# Official Meta WhatsApp Cloud API settings (100% cloud-native, zero Chrome)
META_WA_PHONE_NUMBER_ID = os.getenv("META_WA_PHONE_NUMBER_ID", "")
META_WA_ACCESS_TOKEN = os.getenv("META_WA_ACCESS_TOKEN", "")
META_WA_BUSINESS_ACCOUNT_ID = os.getenv("META_WA_BUSINESS_ACCOUNT_ID", "")

# Email-to-SMS Gateway settings (free SMS via carrier email)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # Use Google App Password if using Gmail

# CSV Data File Path
CLIENTS_CSV_PATH = BASE_DIR / "clients.csv"
