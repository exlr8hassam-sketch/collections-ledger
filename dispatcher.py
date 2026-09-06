import logging
import smtplib
from pathlib import Path
from email.mime.text import MIMEText
from typing import Dict, Any
import requests
import config

logger = logging.getLogger("ReminderDispatcher")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class BaseDispatcher:
    """Base class for all message dispatchers."""
    def send(self, to: str, message: str, client_info: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def send_pdf(self, to: str, pdf_path: str, caption: str, client_info: Dict[str, Any]) -> bool:
        return self.send(to, caption, client_info)


def safe_print(text: str):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', errors='backslashreplace').decode('ascii'))


class SimulationDispatcher(BaseDispatcher):
    """
    Simulated Dispatcher.
    Prints the drafted message and delivery parameters to the console without sending real texts.
    Perfect for safe testing and dry runs.
    """
    def send(self, to: str, message: str, client_info: Dict[str, Any]) -> bool:
        border = "=" * 64
        safe_print(f"\n{border}")
        safe_print(f" [SIMULATION] Outgoing Payment Reminder Text")
        safe_print(f" Recipient : {client_info.get('client_name')} ({to})")
        safe_print(f" Invoice   : {client_info.get('invoice_number')} | Due: {client_info.get('due_date')}")
        safe_print(f" Amount    : {client_info.get('currency', '$')} {client_info.get('amount_due')}")
        safe_print(f"{'-' * 64}")
        safe_print(message)
        safe_print(f"{border}\n")
        return True


class EmailToSmsDispatcher(BaseDispatcher):
    """
    100% Free Carrier Email-to-SMS Gateway.
    Sends an email to the carrier's gateway address (e.g., 5551234567@vtext.com)
    which delivers as a standard SMS on the client's phone.
    """
    CARRIER_GATEWAYS = {
        "verizon": "vtext.com",
        "att": "txt.att.net",
        "tmobile": "tmomail.net",
        "sprint": "messaging.sprintpcs.com",
        "cricket": "mms.cricketwireless.net",
        "uscellular": "email.uscc.net",
        "boost": "myboostmobile.com"
    }

    def send(self, to: str, message: str, client_info: Dict[str, Any]) -> bool:
        carrier = client_info.get("carrier", "").lower().strip()
        gateway = self.CARRIER_GATEWAYS.get(carrier)

        # Normalize phone number (digits only for gateway email)
        clean_number = "".join(filter(str.isdigit, to))
        if len(clean_number) > 10 and clean_number.startswith("1"):
            clean_number = clean_number[1:]

        if not gateway:
            logger.warning(
                f"No known carrier gateway for '{carrier}'. "
                f"Available: {', '.join(self.CARRIER_GATEWAYS.keys())}. Falling back to simulation."
            )
            return SimulationDispatcher().send(to, message, client_info)

        if not config.SMTP_EMAIL or not config.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured in config.py / .env. Falling back to simulation.")
            return SimulationDispatcher().send(to, message, client_info)

        recipient_email = f"{clean_number}@{gateway}"
        logger.info(f"Sending free Email-to-SMS to {recipient_email}")

        try:
            msg = MIMEText(message)
            msg["Subject"] = f"Payment Reminder: {client_info.get('invoice_number')}"
            msg["From"] = config.SMTP_EMAIL
            msg["To"] = recipient_email

            with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_EMAIL, [recipient_email], msg.as_string())

            logger.info(f"Successfully sent SMS via carrier gateway to {to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Email-to-SMS: {e}")
            return False


class TelegramDispatcher(BaseDispatcher):
    """
    100% Free Telegram Bot Dispatcher.
    Sends instant direct message via Telegram Bot API.
    """
    def send(self, to: str, message: str, client_info: Dict[str, Any]) -> bool:
        if not config.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram Bot Token not configured. Falling back to simulation.")
            return SimulationDispatcher().send(to, message, client_info)

        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": to,  # For Telegram, 'to' is the chat_id
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Successfully sent Telegram reminder to {to}")
                return True
            else:
                logger.error(f"Telegram API returned error: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram dispatch failed: {e}")
            return False


class TwilioDispatcher(BaseDispatcher):
    """
    Twilio SMS Dispatcher (for Twilio trial or paid account).
    """
    def send(self, to: str, message: str, client_info: Dict[str, Any]) -> bool:
        if not config.TWILIO_ACCOUNT_SID or not config.TWILIO_AUTH_TOKEN or not config.TWILIO_FROM_NUMBER:
            logger.warning("Twilio credentials not configured. Falling back to simulation.")
            return SimulationDispatcher().send(to, message, client_info)

        url = f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json"
        data = {
            "From": config.TWILIO_FROM_NUMBER,
            "To": to,
            "Body": message
        }
        try:
            resp = requests.post(
                url,
                data=data,
                auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
                timeout=10
            )
            if resp.status_code in [200, 201]:
                logger.info(f"Successfully sent Twilio SMS to {to}")
                return True
            else:
                logger.error(f"Twilio error: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Twilio dispatch failed: {e}")
            return False


class WhatsAppDispatcher(BaseDispatcher):
    """
    Direct WhatsApp Dispatcher using the local WhatsApp Web bridge.
    Sends messages directly from your personal/business WhatsApp account.
    """
    def __init__(self, bridge_url: str = "http://localhost:3000"):
        self.bridge_url = bridge_url

    def send(self, to: str, message: str, client_info: Dict[str, Any]) -> bool:
        url = f"{self.bridge_url}/send"
        payload = {
            "phone": to,
            "message": message
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200 and resp.json().get("success"):
                logger.info(f"Successfully sent WhatsApp message to {to}")
                return True
            else:
                logger.error(f"WhatsApp bridge returned error: {resp.text}")
                return False
        except requests.exceptions.ConnectionError:
            logger.error(
                f"Cannot connect to WhatsApp bridge at {self.bridge_url}. "
                f"Please start the bridge in a separate terminal: cd whatsapp-bridge && npm start"
            )
            return False
        except Exception as e:
            logger.error(f"WhatsApp dispatch failed: {e}")
            return False

    def send_pdf(self, to: str, pdf_path: str, caption: str, client_info: Dict[str, Any]) -> bool:
        """Sends an official PDF invoice/receipt document with caption via WhatsApp."""
        url = f"{self.bridge_url}/send-media"
        filename = Path(pdf_path).name
        payload = {
            "phone": to,
            "filePath": str(Path(pdf_path).resolve()),
            "caption": caption,
            "filename": filename
        }
        try:
            resp = requests.post(url, json=payload, timeout=45)
            if resp.status_code == 200 and resp.json().get("success"):
                logger.info(f"Successfully sent WhatsApp PDF document to {to} ({filename})")
                return True
            else:
                logger.error(f"WhatsApp bridge returned error sending PDF: {resp.text}. Falling back to text.")
                return self.send(to, caption, client_info)
        except Exception as e:
            logger.error(f"WhatsApp PDF dispatch failed: {e}. Falling back to text.")
            return self.send(to, caption, client_info)


def get_dispatcher(mode: str = None) -> BaseDispatcher:
    """Factory function to retrieve the configured dispatcher."""
    selected = (mode or config.DISPATCHER_MODE).lower()
    if selected == "whatsapp":
        return WhatsAppDispatcher()
    elif selected == "email_to_sms":
        return EmailToSmsDispatcher()
    elif selected == "telegram":
        return TelegramDispatcher()
    elif selected == "twilio":
        return TwilioDispatcher()
    else:
        return SimulationDispatcher()
