import csv
import datetime
import logging
import random
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple
import config
from dispatcher import get_dispatcher, BaseDispatcher
from pdf_generator import generate_invoice_pdf

logger = logging.getLogger("PaymentAgent")


class PaymentReminderAgent:
    """
    Autonomous Payment Reminder Agent.
    Evaluates client invoice records, reasons about urgency, drafts tailored text messages
    using Gemini AI, and dispatches them via the selected channel.
    """

    def __init__(self, csv_path: Path = None, dispatcher: BaseDispatcher = None):
        self.csv_path = csv_path or config.CLIENTS_CSV_PATH
        self.dispatcher = dispatcher or get_dispatcher()
        self.policy = config.REMINDER_POLICY
        self.payment_info = config.PAYMENT_DETAILS
        self.gemini_client = None

        if config.GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
                logger.info(f"Initialized Gemini AI engine using model {self.policy['gemini_model']}")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}. Falling back to smart templates.")

    def load_clients(self) -> List[Dict[str, Any]]:
        """Load clients from the CSV storage."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Clients file not found at {self.csv_path}")

        clients = []
        with open(self.csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                clients.append(dict(row))
        return clients

    def save_clients(self, clients: List[Dict[str, Any]]) -> None:
        """Save updated client records back to the CSV storage."""
        if not clients:
            return

        fieldnames = list(clients[0].keys())
        with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(clients)

    def evaluate_client(self, client: Dict[str, Any], current_date: datetime.date) -> Tuple[bool, str, str]:
        """
        Agent reasoning logic:
        Determines whether a client should be reminded today and categorizes the urgency.
        Returns: (should_remind: bool, category: str, reason: str)
        """
        status = client.get("status", "").strip().lower()
        if status == "paid":
            return False, "SKIP", "Invoice is already paid."

        reminders_sent = int(client.get("reminders_sent") or 0)
        if reminders_sent >= self.policy["max_reminders"]:
            return False, "SKIP", f"Maximum reminders ({self.policy['max_reminders']}) already reached."

        # Parse due date
        due_date_str = client.get("due_date", "").strip()
        try:
            due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            return False, "ERROR", f"Invalid due_date format: '{due_date_str}' (expected YYYY-MM-DD)."

        delta_days = (due_date - current_date).days
        is_overdue = delta_days < 0

        # Required gap: if delayed/overdue, use overdue_gap_days, otherwise cooldown_days
        overdue_gap = int(self.policy.get("overdue_gap_days") or self.policy.get("cooldown_days") or 2)
        upcoming_gap = int(self.policy.get("cooldown_days") or 2)
        required_gap = overdue_gap if is_overdue else upcoming_gap

        # Check last reminded cooldown/gap
        last_reminded_str = client.get("last_reminded_date", "").strip()
        if last_reminded_str:
            try:
                last_date = datetime.datetime.strptime(last_reminded_str, "%Y-%m-%d").date()
                days_since_last = (current_date - last_date).days
                if days_since_last < required_gap:
                    status_lbl = f"overdue gap is {required_gap} days" if is_overdue else f"cooldown is {required_gap} days"
                    return False, "COOLDOWN", f"Reminded {days_since_last} day(s) ago ({status_lbl})."
            except ValueError:
                pass  # Ignore invalid date, proceed with check

        advance_days = int(self.policy.get("advance_notice_days", 3))

        if delta_days > advance_days:
            return False, "FUTURE", f"Due in {delta_days} days (reminder starts {advance_days} days prior)."
        elif delta_days > 0:
            return True, "UPCOMING", f"Payment due in {delta_days} day(s)."
        elif delta_days == 0:
            return True, "DUE_TODAY", "Payment is due today."
        else:
            return True, "OVERDUE", f"Payment is overdue by {abs(delta_days)} day(s)."

    def compose_message(
        self,
        client: Dict[str, Any],
        category: str,
        current_date: datetime.date,
        custom_templates: Dict[str, str] = None,
        system_instruction_override: str = None
    ) -> str:
        """
        Generates a human-like, non-spammy reminder text using Gemini AI
        (or smart heuristic fallback / custom templates).
        """
        if custom_templates and category in custom_templates and custom_templates[category].strip():
            template_text = custom_templates[category]
            name = client.get("client_name", "")
            amount = f"{client.get('currency', '$')}{client.get('amount_due', '')}"
            inv = client.get("invoice_number", "Invoice")
            due = client.get("due_date", "")
            bank = self.payment_info["bank_name"]
            acct = self.payment_info["iban"] or self.payment_info["account_number"]
            title = self.payment_info["account_title"]
            contact = self.payment_info.get("support_contact", "")
            
            return template_text.format(
                name=name,
                invoice=inv,
                amount=amount,
                due_date=due,
                bank=bank,
                account=acct,
                title=title,
                contact=contact
            )

        if self.gemini_client:
            try:
                return self._compose_with_gemini(client, category, current_date, system_instruction_override)
            except Exception as e:
                logger.error(f"Gemini generation error: {e}. Using fallback template.")

        return self._compose_with_template(client, category)

    def _compose_with_gemini(
        self,
        client: Dict[str, Any],
        category: str,
        current_date: datetime.date,
        system_instruction_override: str = None
    ) -> str:
        """Prompts Gemini to generate a tailored text message."""
        due_date = client.get("due_date")
        amount = f"{client.get('currency', '$')}{client.get('amount_due')}"
        invoice = client.get("invoice_number", "N/A")
        client_name = client.get("client_name")

        system_instruction = system_instruction_override or (
            "You are an accounts receivable billing agent for our company. "
            "Write a clean, structured WhatsApp invoice reminder message for a client regarding their payment. "
            "Formatting style:\n"
            "- Use WhatsApp markdown: bold headers with asterisks (*INVOICE*), bullet points, emojis (🧾, 👤, 📄, 📅, 💰, 🏦).\n"
            "- Include: Client Name, Invoice #, Due Date, Amount Due, and Receiving Bank/Account Details.\n"
            "- Tone requirements:\n"
            "  * UPCOMING: Friendly, polite courtesy heads-up.\n"
            "  * DUE_TODAY: Clear, direct, professional reminder that payment is due today.\n"
            "  * OVERDUE: Professional, firm, but respectful follow-up.\n"
            "Constraints:\n"
            "- Do not include placeholders like '[Your Name]' or '[Company]'; use the provided data directly.\n"
            "- Return ONLY the final message text to send, no markdown code fence or extra intro."
        )

        user_prompt = f"""
Current Date: {current_date}
Urgency Category: {category}
Client Name: {client_name}
Invoice Number: {invoice}
Amount Due: {amount}
Due Date: {due_date}

Our Bank Payment Details:
Bank: {self.payment_info['bank_name']}
Account Title: {self.payment_info['account_title']}
Account Number / IBAN: {self.payment_info['iban'] or self.payment_info['account_number']}
Swift/Routing: {self.payment_info.get('routing_or_swift', '')}
Support Contact: {self.payment_info['support_contact']}
"""
        response = self.gemini_client.models.generate_content(
            model=self.policy["gemini_model"],
            contents=[system_instruction, user_prompt]
        )
        return response.text.strip()

    def _compose_with_template(self, client: Dict[str, Any], category: str) -> str:
        """Smart fallback template when Gemini API key is not yet set."""
        name = client.get("client_name")
        amount = f"{client.get('currency', '$')}{client.get('amount_due')}"
        inv = client.get("invoice_number", "Invoice")
        due = client.get("due_date")
        bank = self.payment_info["bank_name"]
        acct = self.payment_info["iban"] or self.payment_info["account_number"]
        title = self.payment_info["account_title"]

        if category == "UPCOMING":
            return (
                f"🧾 *PAYMENT REMINDER / INVOICE*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 *Client:* {name}\n"
                f"📄 *Invoice #:* {inv}\n"
                f"📅 *Due Date:* {due} (Upcoming)\n"
                f"💰 *Amount Due:* *{amount}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏦 *PAYMENT DETAILS:*\n"
                f"• *Bank:* {bank}\n"
                f"• *Account Title:* {title}\n"
                f"• *Account / IBAN:* {acct}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Please disregard if already paid. Thank you! 🙏"
            )
        elif category == "DUE_TODAY":
            return (
                f"🧾 *INVOICE DUE TODAY*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 *Client:* {name}\n"
                f"📄 *Invoice #:* {inv}\n"
                f"📅 *Due Date:* Today ({due})\n"
                f"💰 *Total Due:* *{amount}*\n"
                f"📌 *Status:* Pending\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏦 *PAYMENT INSTRUCTIONS:*\n"
                f"• *Bank:* {bank}\n"
                f"• *Account Title:* {title}\n"
                f"• *Account / IBAN:* {acct}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Please reply with the payment screenshot or receipt once transferred. Thank you! 🙏"
            )
        else:  # OVERDUE
            return (
                f"⚠️ *OVERDUE PAYMENT NOTICE*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 *Client:* {name}\n"
                f"📄 *Invoice #:* {inv}\n"
                f"📅 *Due Date:* {due} (OVERDUE)\n"
                f"💰 *Outstanding Balance:* *{amount}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏦 *TRANSFER TO:*\n"
                f"• *Bank:* {bank}\n"
                f"• *Account Title:* {title}\n"
                f"• *Account / IBAN:* {acct}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Kindly settle this payment at your earliest convenience. Contact {self.payment_info['support_contact']} for any inquiries."
            )

    def process_reminders(self, dry_run: bool = False, target_client_id: str = None, attach_pdf: bool = True) -> List[Dict[str, Any]]:
        """
        Main execution cycle:
        Inspects all clients, evaluates policies, drafts texts, attaches official PDF invoices, and dispatches.
        """
        current_date = datetime.date.today()
        clients = self.load_clients()
        results = []

        logger.info(f"Running Payment Reminder Cycle for {current_date} (Dry Run: {dry_run}, PDF: {attach_pdf})")

        for client in clients:
            cid = client.get("client_id")
            if target_client_id and cid != target_client_id:
                continue

            should_remind, category, reason = self.evaluate_client(client, current_date)

            if not should_remind:
                results.append({
                    "client_id": cid,
                    "name": client.get("client_name"),
                    "action": "SKIPPED",
                    "category": category,
                    "reason": reason
                })
                continue

            # Draft the personalized text
            message = self.compose_message(client, category, current_date)
            phone = client.get("phone", "")
            sent_success = False

            pdf_path = None
            if attach_pdf:
                try:
                    pdf_path = generate_invoice_pdf(client, self.payment_info, is_paid=(client.get("status", "").lower() == "paid"))
                except Exception as e:
                    logger.error(f"Error generating PDF invoice for {cid}: {e}")

            if dry_run:
                from dispatcher import SimulationDispatcher
                SimulationDispatcher().send(phone, message, client)
                sent_success = True
            else:
                if pdf_path and hasattr(self.dispatcher, 'send_pdf'):
                    sent_success = self.dispatcher.send_pdf(phone, pdf_path, message, client)
                else:
                    sent_success = self.dispatcher.send(phone, message, client)

                if sent_success:
                    delay = random.uniform(4.0, 7.0)
                    logger.info(f"Pacing delay: waiting {delay:.1f}s before processing next client...")
                    time.sleep(delay)

            if sent_success:
                client["reminders_sent"] = str(int(client.get("reminders_sent") or 0) + 1)
                client["last_reminded_date"] = str(current_date)

            results.append({
                "client_id": cid,
                "name": client.get("client_name"),
                "action": "REMINDED" if sent_success else "FAILED",
                "category": category,
                "reason": reason,
                "message": message,
                "pdf_path": pdf_path
            })

        if not dry_run:
            self.save_clients(clients)
            logger.info("Saved updated reminder timestamps to clients.csv")

        return results

    def reload_config(self):
        """Reload configuration from config.py."""
        import importlib
        importlib.reload(config)
        self.policy = config.REMINDER_POLICY
        self.payment_info = config.PAYMENT_DETAILS
        self.dispatcher = get_dispatcher()
        if config.GEMINI_API_KEY and not self.gemini_client:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
            except Exception:
                pass

    def send_to_client(
        self,
        client_id: str,
        custom_message: str = None,
        dry_run: bool = False,
        attach_pdf: bool = True
    ) -> Dict[str, Any]:
        """Send a reminder with attached PDF invoice to a specific client."""
        current_date = datetime.date.today()
        clients = self.load_clients()
        target = None
        target_idx = -1
        for idx, c in enumerate(clients):
            if c.get("client_id") == client_id:
                target = c
                target_idx = idx
                break

        if not target:
            return {"success": False, "error": f"Client {client_id} not found."}

        should_remind, category, reason = self.evaluate_client(target, current_date)

        if custom_message and custom_message.strip():
            message = custom_message.strip()
        else:
            cat_to_use = category if category not in ["SKIP", "COOLDOWN", "ERROR"] else "DUE_TODAY"
            message = self.compose_message(target, cat_to_use, current_date)

        phone = target.get("phone", "")
        if not phone:
            return {"success": False, "error": "Client has no phone number."}

        pdf_path = None
        if attach_pdf:
            try:
                pdf_path = generate_invoice_pdf(target, self.payment_info, is_paid=(target.get("status", "").lower() == "paid"))
            except Exception as e:
                logger.error(f"Error generating PDF invoice for {client_id}: {e}")

        if dry_run:
            from dispatcher import SimulationDispatcher
            SimulationDispatcher().send(phone, message, target)
            sent = True
        else:
            if pdf_path and hasattr(self.dispatcher, 'send_pdf'):
                sent = self.dispatcher.send_pdf(phone, pdf_path, message, target)
            else:
                sent = self.dispatcher.send(phone, message, target)

        if sent and not dry_run:
            target["reminders_sent"] = str(int(target.get("reminders_sent") or 0) + 1)
            target["last_reminded_date"] = str(current_date)
            clients[target_idx] = target
            self.save_clients(clients)

        err_msg = getattr(self.dispatcher, 'last_error', None)
        return {
            "success": sent,
            "error": err_msg or ("WhatsApp is not ready. Please scan the QR code or link your phone." if not sent else None),
            "client_id": client_id,
            "name": target.get("client_name"),
            "phone": phone,
            "message": message,
            "pdf_path": pdf_path,
            "category": category,
            "reason": reason
        }

    def confirm_payment(
        self,
        client_id: str,
        custom_thank_you: str = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Confirms a client's payment:
        1. Updates client status to Paid in clients.csv
        2. Generates an official settled PAID Invoice PDF
        3. Sends a warm Thank You WhatsApp message with the Paid PDF receipt attached
        """
        current_date = datetime.date.today()
        clients = self.load_clients()
        target = None
        target_idx = -1
        for idx, c in enumerate(clients):
            if c.get("client_id") == client_id:
                target = c
                target_idx = idx
                break

        if not target:
            return {"success": False, "error": f"Client {client_id} not found."}

        # Mark Paid in memory and CSV
        target["status"] = "Paid"
        target["last_reminded_date"] = str(current_date)
        clients[target_idx] = target
        if not dry_run:
            self.save_clients(clients)

        name = target.get("client_name", "Valued Client")
        inv = target.get("invoice_number", "Invoice")
        amount = f"{target.get('currency', 'PKR')} {float(target.get('amount_due', 0)):,.2f}"
        phone = target.get("phone", "")

        thank_you_msg = custom_thank_you or (
            f"✅ *PAYMENT RECEIVED & CONFIRMED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Dear {name},\n\n"
            f"We gratefully acknowledge receipt of your payment of *{amount}* for Invoice #{inv}.\n"
            f"Your account is now fully settled. Attached is your official receipt for your records.\n\n"
            f"Thank you for your business and partnership! 🙏"
        )

        # Generate official PAID invoice PDF
        paid_pdf_path = generate_invoice_pdf(target, self.payment_info, is_paid=True)

        if dry_run:
            from dispatcher import SimulationDispatcher
            SimulationDispatcher().send(phone, thank_you_msg, target)
            sent = True
        else:
            if hasattr(self.dispatcher, 'send_pdf'):
                sent = self.dispatcher.send_pdf(phone, paid_pdf_path, thank_you_msg, target)
            else:
                sent = self.dispatcher.send(phone, thank_you_msg, target)

        return {
            "success": sent,
            "client_id": client_id,
            "name": name,
            "phone": phone,
            "status": "Paid",
            "pdf_path": paid_pdf_path,
            "message": thank_you_msg
        }

    def roll_client_next_month(self, client_id: str) -> Dict[str, Any]:
        """
        Advances a client to next month's billing cycle:
        - Advances due_date by 1 month (same day of the month)
        - Increments invoice_number (e.g. INV-001 -> INV-002)
        - Resets status to Pending
        - Resets reminders_sent to 0
        - Clears last_reminded_date
        """
        clients = self.load_clients()
        target = None
        target_idx = -1
        for idx, c in enumerate(clients):
            if c.get("client_id") == client_id:
                target = c
                target_idx = idx
                break

        if not target:
            return {"success": False, "error": f"Client {client_id} not found."}

        due_str = target.get("due_date", "").strip()
        try:
            current_due = datetime.datetime.strptime(due_str, "%Y-%m-%d").date()
        except Exception:
            current_due = datetime.date.today()

        next_due = get_next_month_date(current_due)
        old_inv = target.get("invoice_number", "INV-001")
        next_inv = increment_invoice_number(old_inv)

        target["due_date"] = str(next_due)
        target["invoice_number"] = next_inv
        target["status"] = "Pending"
        target["reminders_sent"] = "0"
        target["last_reminded_date"] = ""

        clients[target_idx] = target
        self.save_clients(clients)

        logger.info(f"Rolled client {client_id} to next month: Due {next_due}, Invoice {next_inv}")
        return {
            "success": True,
            "client_id": client_id,
            "client_name": target.get("client_name"),
            "old_invoice": old_inv,
            "new_invoice": next_inv,
            "new_due_date": str(next_due),
            "client": target
        }


def get_next_month_date(d: datetime.date) -> datetime.date:
    """Calculates the same calendar day in the next month (handling month-end days)."""
    import calendar
    year = d.year + (d.month // 12)
    month = (d.month % 12) + 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(d.day, max_day)
    return datetime.date(year, month, day)


def increment_invoice_number(inv: str) -> str:
    """Increments the trailing number in an invoice string (e.g. 'INV-001' -> 'INV-002', '1' -> '2')."""
    import re
    match = re.search(r'(\d+)$', inv)
    if match:
        num_str = match.group(1)
        next_num = int(num_str) + 1
        return inv[:match.start(1)] + f"{next_num:0{len(num_str)}d}"
    return f"{inv}-2"

