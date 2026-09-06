import os
import csv
import datetime
import uuid
import html
from pathlib import Path
from typing import Optional, Dict, Any, List

import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, Response
from pydantic import BaseModel
import requests

import config
from agent import PaymentReminderAgent

app = FastAPI(title="Payment Reminder Agent Dashboard")
agent = PaymentReminderAgent()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)


# -----------------------------------------------------------------------------
# Pydantic Request Models
# -----------------------------------------------------------------------------
class ClientCreate(BaseModel):
    client_name: str
    phone: str
    amount_due: float
    currency: Optional[str] = "PKR"
    invoice_number: Optional[str] = None
    due_date: str  # YYYY-MM-DD
    status: Optional[str] = "Pending"
    notes: Optional[str] = ""


class ClientUpdate(BaseModel):
    client_name: Optional[str] = None
    phone: Optional[str] = None
    amount_due: Optional[float] = None
    currency: Optional[str] = None
    invoice_number: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class PreviewRequest(BaseModel):
    client_id: str
    category: Optional[str] = None
    custom_templates: Optional[Dict[str, str]] = None
    system_instruction: Optional[str] = None


class SendSingleRequest(BaseModel):
    client_id: str
    custom_message: Optional[str] = None
    dry_run: Optional[bool] = False
    attach_pdf: Optional[bool] = True


class SendAllRequest(BaseModel):
    dry_run: Optional[bool] = False
    attach_pdf: Optional[bool] = True


class ConfirmPaymentRequest(BaseModel):
    custom_thank_you: Optional[str] = None
    dry_run: Optional[bool] = False


class IncomingMessagePayload(BaseModel):
    phone: str
    text: Optional[str] = ""
    has_media: Optional[bool] = False
    timestamp: Optional[str] = None


class PaymentConfigUpdate(BaseModel):
    bank_name: Optional[str] = None
    account_title: Optional[str] = None
    account_number: Optional[str] = None
    iban: Optional[str] = None
    support_contact: Optional[str] = None
    advance_notice_days: Optional[int] = None
    overdue_gap_days: Optional[int] = None
    cooldown_days: Optional[int] = None
    auto_roll_monthly: Optional[bool] = None


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/status")
def get_system_status():
    """Checks the status of the WhatsApp Web bridge or Meta Cloud API."""
    meta_id = getattr(config, "META_WA_PHONE_NUMBER_ID", "") or os.getenv("META_WA_PHONE_NUMBER_ID")
    meta_token = getattr(config, "META_WA_ACCESS_TOKEN", "") or os.getenv("META_WA_ACCESS_TOKEN")

    if meta_id and meta_token:
        return {
            "bridge_online": True,
            "whatsapp_ready": True,
            "bridge_status": "connected",
            "gateway": "Meta WhatsApp Cloud API",
            "phone_number_id": meta_id,
            "user_phone": "+1 (555) 675-8522",
            "pairing_code": None,
            "bridge_url": "https://graph.facebook.com"
        }

    bridge_url = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")
    try:
        resp = requests.get(f"{bridge_url}/status", timeout=2)
        data = resp.json()
        return {
            "bridge_online": True,
            "whatsapp_ready": data.get("ready", False),
            "bridge_status": data.get("status", "unknown"),
            "pairing_code": data.get("pairingCode"),
            "user_phone": data.get("userPhone"),
            "bridge_url": bridge_url
        }
    except Exception as e:
        return {
            "bridge_online": False,
            "whatsapp_ready": False,
            "bridge_status": "offline",
            "error": str(e),
            "bridge_url": bridge_url
        }


@app.post("/api/whatsapp/disconnect")
def disconnect_whatsapp():
    """Disconnects the current WhatsApp session to link another account."""
    bridge_url = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")
    try:
        resp = requests.post(f"{bridge_url}/disconnect", timeout=5)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/whatsapp/pair")
def request_whatsapp_pairing(payload: dict):
    """Requests an 8-character WhatsApp pairing code for a specific phone number."""
    bridge_url = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")
    try:
        resp = requests.post(f"{bridge_url}/pair", json=payload, timeout=8)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/qr-img")
@app.get("/api/whatsapp/qr")
def get_whatsapp_qr():
    """Proxies the WhatsApp QR code image so it works on mobile devices and over the internet."""
    bridge_url = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")
    try:
        resp = requests.get(f"{bridge_url}/qr-img", timeout=3)
        if resp.status_code == 200:
            return Response(content=resp.content, media_type="image/png")
    except Exception:
        pass
    qr_file = BASE_DIR / "whatsapp-bridge" / "qr.png"
    if qr_file.exists():
        return FileResponse(qr_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="QR code not available")


@app.get("/qr", response_class=HTMLResponse)
def serve_qr_page():
    """Serves the live auto-refreshing QR code scanning page."""
    bridge_url = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")
    try:
        resp = requests.get(f"{bridge_url}/qr", timeout=3)
        if resp.status_code == 200:
            return HTMLResponse(content=resp.text)
    except Exception:
        pass
    return HTMLResponse("<h2>QR generator loading, please refresh in 5 seconds...</h2>")


@app.get("/api/clients")
def get_all_clients():
    """Returns all clients enriched with evaluation status and category."""
    try:
        clients = agent.load_clients()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    today = datetime.date.today()
    enriched = []
    
    for c in clients:
        should_remind, category, reason = agent.evaluate_client(c, today)
        c_copy = dict(c)
        c_copy["evaluation"] = {
            "should_remind": should_remind,
            "category": category,
            "reason": reason
        }
        enriched.append(c_copy)

    # Compute summary stats
    pending_amount = sum(
        float(c.get("amount_due") or 0) for c in clients 
        if c.get("status", "").strip().lower() != "paid"
    )
    due_today_count = sum(
        1 for c in enriched if c["evaluation"]["category"] == "DUE_TODAY" and c.get("status", "").strip().lower() != "paid"
    )
    overdue_count = sum(
        1 for c in enriched if c["evaluation"]["category"] == "OVERDUE" and c.get("status", "").strip().lower() != "paid"
    )
    total_clients = len(clients)

    return {
        "clients": enriched,
        "stats": {
            "pending_amount": pending_amount,
            "due_today_count": due_today_count,
            "overdue_count": overdue_count,
            "total_clients": total_clients
        }
    }


def normalize_phone_number(phone: str) -> str:
    cleaned = "".join(filter(str.isdigit, phone or ""))
    if cleaned.startswith("03") and len(cleaned) == 11:
        return "+92" + cleaned[1:]
    elif cleaned.startswith("3") and len(cleaned) == 10:
        return "+92" + cleaned
    elif cleaned.startswith("92") and len(cleaned) == 12:
        return "+" + cleaned
    return (phone or "").strip()


@app.post("/api/clients")
def create_client(payload: ClientCreate):
    """Adds a new client to clients.csv."""
    clients = agent.load_clients()
    
    # Generate unique client ID
    existing_ids = [c.get("client_id", "") for c in clients]
    next_num = len(clients) + 1
    new_id = f"CLI-{next_num:03d}"
    while new_id in existing_ids:
        next_num += 1
        new_id = f"CLI-{next_num:03d}"

    inv = payload.invoice_number or f"INV-{next_num:03d}"

    new_record = {
        "client_id": new_id,
        "client_name": payload.client_name.strip(),
        "phone": normalize_phone_number(payload.phone),
        "carrier": "",
        "amount_due": str(payload.amount_due),
        "currency": payload.currency.strip().upper(),
        "invoice_number": inv.strip(),
        "due_date": payload.due_date.strip(),
        "status": payload.status.strip(),
        "reminders_sent": "0",
        "last_reminded_date": "",
        "notes": (payload.notes or "").strip()
    }

    clients.append(new_record)
    agent.save_clients(clients)
    return {"success": True, "client": new_record}


@app.put("/api/clients/{client_id}")
def update_client(client_id: str, payload: ClientUpdate):
    """Updates an existing client. If status is changed to Paid, automatically confirms and sends receipt."""
    clients = agent.load_clients()
    found = False
    updated_record = None
    was_pending_now_paid = False

    for i, c in enumerate(clients):
        if c.get("client_id") == client_id:
            found = True
            prev_status = (c.get("status") or "").strip().lower()
            if payload.client_name is not None:
                c["client_name"] = payload.client_name.strip()
            if payload.phone is not None:
                c["phone"] = normalize_phone_number(payload.phone)
            if payload.amount_due is not None:
                c["amount_due"] = str(payload.amount_due)
            if payload.currency is not None:
                c["currency"] = payload.currency.strip().upper()
            if payload.invoice_number is not None:
                c["invoice_number"] = payload.invoice_number.strip()
            if payload.due_date is not None:
                c["due_date"] = payload.due_date.strip()
            if payload.status is not None:
                new_st = payload.status.strip()
                if new_st.lower() == "paid" and prev_status != "paid":
                    was_pending_now_paid = True
                c["status"] = new_st
            if payload.notes is not None:
                c["notes"] = payload.notes.strip()
            
            clients[i] = c
            updated_record = c
            break

    if not found:
        raise HTTPException(status_code=404, detail="Client not found")

    agent.save_clients(clients)

    if was_pending_now_paid:
        agent.confirm_payment(client_id=client_id)

    return {"success": True, "client": updated_record}


@app.patch("/api/clients/{client_id}/toggle-status")
def toggle_client_status(client_id: str):
    """
    Toggles status between 'Pending' and 'Paid'.
    When changing from Pending to Paid, automatically confirms payment:
    generates official Paid PDF invoice and sends Thank You message with PDF on WhatsApp.
    """
    clients = agent.load_clients()
    target = next((c for c in clients if c.get("client_id") == client_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Client not found")

    curr = (target.get("status") or "").strip().lower()
    if curr != "paid":
        # Automatically confirm payment & dispatch Paid receipt PDF on WhatsApp
        confirm_res = agent.confirm_payment(client_id=client_id)
        return {
            "success": True,
            "client_id": client_id,
            "new_status": "Paid",
            "receipt_sent": confirm_res.get("success", False),
            "client_name": target.get("client_name"),
            "pdf_path": confirm_res.get("pdf_path")
        }
    else:
        # Revert back to Pending
        for i, c in enumerate(clients):
            if c.get("client_id") == client_id:
                c["status"] = "Pending"
                clients[i] = c
                break
        agent.save_clients(clients)
        return {
            "success": True,
            "client_id": client_id,
            "new_status": "Pending",
            "receipt_sent": False,
            "client_name": target.get("client_name")
        }


@app.get("/api/webhook")
def verify_meta_webhook(request: Request):
    """Verifies the webhook endpoint with Meta WhatsApp Cloud Platform."""
    verify_token = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "collections_ledger_secure_token")
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == verify_token:
        logger.info("[✓] Meta Webhook verified successfully!")
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@app.post("/api/webhook")
async def handle_meta_webhook(request: Request):
    """Handles incoming WhatsApp button replies (e.g. 'I Have Paid')."""
    try:
        body = await request.json()
        entry = body.get("entry", [])
        if entry:
            changes = entry[0].get("changes", [])
            if changes:
                value = changes[0].get("value", {})
                messages = value.get("messages", [])
                if messages:
                    msg = messages[0]
                    if msg.get("type") == "interactive":
                        btn_reply = msg.get("interactive", {}).get("button_reply", {})
                        btn_id = btn_reply.get("id", "")
                        btn_title = btn_reply.get("title", "")
                        from_phone = msg.get("from", "")
                        logger.info(f"[*] Client {from_phone} tapped button: {btn_title} ({btn_id})")

                        if btn_id.startswith("paid_") or "paid" in btn_id.lower():
                            raw_id = btn_id.replace("paid_", "").replace("btn_paid_", "")
                            clients = agent.load_clients()
                            for c in clients:
                                if c.get("client_id") == raw_id or raw_id in c.get("invoice_number", ""):
                                    c["status"] = "Paid"
                                    c["notes"] = f"Settlement reported via WhatsApp button on {datetime.date.today()}"
                                    break
                            agent.save_clients(clients)
                            logger.info(f"[✓] Client settled via WhatsApp button: {raw_id}")
    except Exception as e:
        logger.warning(f"Webhook processing error: {e}")
    return {"status": "success"}


@app.delete("/api/clients/{client_id}")
def delete_client(client_id: str):
    """Deletes a client from clients.csv."""
    clients = agent.load_clients()
    initial_len = len(clients)
    clients = [c for c in clients if c.get("client_id") != client_id]

    if len(clients) == initial_len:
        raise HTTPException(status_code=404, detail="Client not found")

    agent.save_clients(clients)
    return {"success": True, "client_id": client_id}


@app.post("/api/preview")
def preview_message(payload: PreviewRequest):
    """Generates a message preview for a specific client."""
    clients = agent.load_clients()
    client = next((c for c in clients if c.get("client_id") == payload.client_id), None)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    today = datetime.date.today()
    should_remind, evaluated_category, reason = agent.evaluate_client(client, today)
    
    category = payload.category or (
        evaluated_category if evaluated_category not in ["SKIP", "COOLDOWN", "ERROR"] else "DUE_TODAY"
    )

    message = agent.compose_message(
        client=client,
        category=category,
        current_date=today,
        custom_templates=payload.custom_templates,
        system_instruction_override=payload.system_instruction
    )

    return {
        "client_id": payload.client_id,
        "name": client.get("client_name"),
        "phone": client.get("phone"),
        "category": category,
        "reason": reason,
        "message": message
    }


@app.post("/api/send-single")
def send_single_reminder(payload: SendSingleRequest):
    """Dispatches a reminder (with attached PDF invoice by default) to a single client."""
    result = agent.send_to_client(
        client_id=payload.client_id,
        custom_message=payload.custom_message,
        dry_run=payload.dry_run,
        attach_pdf=payload.attach_pdf
    )
    if not result.get("success") and not payload.dry_run:
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/api/send-all")
def send_all_due_reminders(payload: SendAllRequest):
    """Dispatches reminders (with attached PDF invoices by default) to all clients currently due or overdue."""
    results = agent.process_reminders(dry_run=payload.dry_run, attach_pdf=payload.attach_pdf)
    
    sent_count = sum(1 for r in results if r.get("action") == "REMINDED")
    skipped_count = sum(1 for r in results if r.get("action") == "SKIPPED")
    failed_count = sum(1 for r in results if r.get("action") == "FAILED")

    return {
        "success": True,
        "dry_run": payload.dry_run,
        "sent_count": sent_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "results": results
    }


@app.post("/api/clients/{client_id}/confirm-payment")
def confirm_client_payment(client_id: str, payload: ConfirmPaymentRequest = ConfirmPaymentRequest()):
    """
    Confirms payment for a client:
    1. Updates status to 'Paid' in clients.csv
    2. Generates updated official settled PAID Invoice PDF
    3. Dispatches thank you WhatsApp message with Paid PDF attached
    4. If auto_roll_monthly is enabled, rolls client to next month's invoice
    """
    result = agent.confirm_payment(
        client_id=client_id,
        custom_thank_you=payload.custom_thank_you,
        dry_run=payload.dry_run
    )
    if not result.get("success") and not payload.dry_run:
        return JSONResponse(status_code=400, content=result)

    if not payload.dry_run and config.REMINDER_POLICY.get("auto_roll_monthly"):
        roll_res = agent.roll_client_next_month(client_id)
        result["auto_rolled"] = roll_res

    return result


@app.post("/api/clients/{client_id}/roll-next-month")
def roll_single_client_next_month(client_id: str):
    """Advances client to next month's invoice: advances due_date by 1 month, increments invoice #, resets status to Pending."""
    result = agent.roll_client_next_month(client_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Failed to roll client"))
    return result


@app.post("/api/clients/roll-all-next-month")
def roll_all_paid_clients_next_month():
    """Advances all currently Paid clients to next month's invoice."""
    clients = agent.load_clients()
    rolled = []
    for c in clients:
        if (c.get("status") or "").strip().lower() == "paid":
            res = agent.roll_client_next_month(c.get("client_id"))
            if res.get("success"):
                rolled.append(res)
    return {"success": True, "rolled_count": len(rolled), "clients": rolled}


@app.get("/api/config")
def get_config():
    """Returns current payment details and policy."""
    return {
        "payment_details": config.PAYMENT_DETAILS,
        "reminder_policy": config.REMINDER_POLICY,
        "dispatcher_mode": config.DISPATCHER_MODE,
        "has_gemini_key": bool(config.GEMINI_API_KEY)
    }


@app.post("/api/config")
def update_config(payload: PaymentConfigUpdate):
    """Updates payment details and policy in-memory and in .env."""
    env_path = BASE_DIR / ".env"
    env_lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            env_lines = f.readlines()

    updates = {}
    if payload.bank_name is not None:
        updates["PAYMENT_BANK_NAME"] = payload.bank_name
        config.PAYMENT_DETAILS["bank_name"] = payload.bank_name
    if payload.account_title is not None:
        updates["PAYMENT_ACCOUNT_TITLE"] = payload.account_title
        config.PAYMENT_DETAILS["account_title"] = payload.account_title
    if payload.account_number is not None:
        updates["PAYMENT_ACCOUNT_NUMBER"] = payload.account_number
        config.PAYMENT_DETAILS["account_number"] = payload.account_number
    if payload.iban is not None:
        updates["PAYMENT_IBAN"] = payload.iban
        config.PAYMENT_DETAILS["iban"] = payload.iban
    if payload.support_contact is not None:
        updates["SUPPORT_CONTACT"] = payload.support_contact
        config.PAYMENT_DETAILS["support_contact"] = payload.support_contact
    if payload.advance_notice_days is not None:
        updates["ADVANCE_NOTICE_DAYS"] = str(payload.advance_notice_days)
        config.REMINDER_POLICY["advance_notice_days"] = payload.advance_notice_days
    if payload.overdue_gap_days is not None:
        updates["OVERDUE_GAP_DAYS"] = str(payload.overdue_gap_days)
        config.REMINDER_POLICY["overdue_gap_days"] = payload.overdue_gap_days
        config.REMINDER_POLICY["cooldown_days"] = payload.overdue_gap_days
    elif payload.cooldown_days is not None:
        updates["OVERDUE_GAP_DAYS"] = str(payload.cooldown_days)
        config.REMINDER_POLICY["overdue_gap_days"] = payload.cooldown_days
        config.REMINDER_POLICY["cooldown_days"] = payload.cooldown_days
    if payload.auto_roll_monthly is not None:
        updates["AUTO_ROLL_MONTHLY"] = "true" if payload.auto_roll_monthly else "false"
        config.REMINDER_POLICY["auto_roll_monthly"] = bool(payload.auto_roll_monthly)

    # Write back to .env
    new_lines = []
    seen_keys = set()
    for line in env_lines:
        line_clean = line.strip()
        if "=" in line_clean and not line_clean.startswith("#"):
            k = line_clean.split("=")[0].strip()
            if k in updates:
                new_lines.append(f'{k}="{updates[k]}"\n')
                seen_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in seen_keys:
            new_lines.append(f'{k}="{v}"\n')

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    agent.reload_config()
    return {"success": True, "updated": updates}


# -----------------------------------------------------------------------------
# Invoice Generation & Print / PDF Route
# -----------------------------------------------------------------------------
@app.get("/invoice/{client_id}", response_class=HTMLResponse)
def generate_invoice_page(client_id: str):
    """Renders a print-ready, professional digital and PDF invoice for a client."""
    clients = agent.load_clients()
    client = next((c for c in clients if c.get("client_id") == client_id), None)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client_name = html.escape(str(client.get("client_name", "Valued Client")))
    phone = html.escape(str(client.get("phone", "N/A")))
    invoice_num = html.escape(str(client.get("invoice_number", f"INV-{client_id}")))
    currency = html.escape(str(client.get("currency", "PKR")))
    try:
        amt_val = float(client.get("amount_due", 0))
        formatted_amt = f"{amt_val:,.2f}"
    except Exception:
        formatted_amt = str(client.get("amount_due", "0.00"))
    
    due_date = html.escape(str(client.get("due_date", "N/A")))
    notes = html.escape(str(client.get("notes", "Professional Services / Account Settlement")))
    status = str(client.get("status", "Pending")).strip()
    is_paid = status.lower() == "paid"

    pay = config.PAYMENT_DETAILS
    bank_name = html.escape(str(pay.get("bank_name", "Bank Transfer")))
    account_title = html.escape(str(pay.get("account_title", "Account Holder")))
    account_number = html.escape(str(pay.get("account_number", "")))
    iban = html.escape(str(pay.get("iban", "")))
    support_contact = html.escape(str(pay.get("support_contact", "")))

    today_str = datetime.date.today().strftime("%d %b %Y")

    status_badge = (
        '<span style="background:#dcfce7;color:#15803d;padding:4px 14px;border-radius:9999px;font-weight:700;font-size:12px;border:1px solid #86efac;">✓ PAID</span>'
        if is_paid else
        '<span style="background:#fee2e2;color:#b91c1c;padding:4px 14px;border-radius:9999px;font-weight:700;font-size:12px;border:1px solid #fca5a5;">⏳ PAYMENT DUE</span>'
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Invoice {invoice_num} - {client_name}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      background: #f1f5f9;
      color: #0f172a;
      padding: 30px 16px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    .action-bar {{
      max-width: 800px;
      width: 100%;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      gap: 12px;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 9px 16px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      border: none;
      transition: all 0.15s ease;
    }}
    .btn-primary {{
      background: #059669;
      color: white;
      box-shadow: 0 4px 12px rgba(5, 150, 105, 0.25);
    }}
    .btn-primary:hover {{ background: #047857; }}
    .btn-secondary {{
      background: white;
      color: #334155;
      border: 1px solid #cbd5e1;
    }}
    .btn-secondary:hover {{ background: #f8fafc; }}
    .invoice-card {{
      max-width: 800px;
      width: 100%;
      background: white;
      border-radius: 16px;
      padding: 48px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.06);
      border: 1px solid #e2e8f0;
    }}
    .header-row {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 2px solid #f1f5f9;
      padding-bottom: 28px;
      margin-bottom: 28px;
    }}
    .company-title {{
      font-size: 22px;
      font-weight: 800;
      color: #0f172a;
      letter-spacing: -0.5px;
    }}
    .company-sub {{
      font-size: 13px;
      color: #64748b;
      margin-top: 4px;
    }}
    .inv-details {{
      text-align: right;
    }}
    .inv-title {{
      font-size: 24px;
      font-weight: 800;
      color: #059669;
      letter-spacing: 0.5px;
    }}
    .inv-meta {{
      font-size: 12px;
      color: #64748b;
      margin-top: 6px;
      line-height: 1.6;
    }}
    .bill-section {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 24px;
      margin-bottom: 32px;
    }}
    .bill-box h4 {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #94a3b8;
      margin-bottom: 8px;
    }}
    .bill-box p {{
      font-size: 14px;
      color: #1e293b;
      line-height: 1.5;
    }}
    .bill-box .client-name {{
      font-weight: 700;
      font-size: 16px;
      color: #0f172a;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 32px;
    }}
    th {{
      background: #f8fafc;
      text-align: left;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #64748b;
      padding: 12px 16px;
      border-top: 1px solid #e2e8f0;
      border-bottom: 1px solid #e2e8f0;
    }}
    th:last-child, td:last-child {{
      text-align: right;
    }}
    td {{
      padding: 16px;
      font-size: 13px;
      border-bottom: 1px solid #f1f5f9;
      color: #334155;
    }}
    .item-desc {{
      font-weight: 600;
      color: #0f172a;
    }}
    .item-sub {{
      font-size: 12px;
      color: #64748b;
      margin-top: 2px;
    }}
    .summary-row {{
      display: flex;
      justify-content: flex-end;
      margin-bottom: 36px;
    }}
    .summary-box {{
      width: 260px;
    }}
    .summary-line {{
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      font-size: 13px;
      color: #64748b;
    }}
    .summary-line.total {{
      border-top: 2px solid #0f172a;
      margin-top: 6px;
      padding-top: 12px;
      font-size: 18px;
      font-weight: 800;
      color: #0f172a;
    }}
    .payment-box {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 20px 24px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    .pay-col h5 {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #059669;
      margin-bottom: 8px;
      font-weight: 700;
    }}
    .pay-item {{
      font-size: 12px;
      color: #475569;
      margin-bottom: 4px;
      line-height: 1.5;
    }}
    .pay-item strong {{
      color: #0f172a;
    }}
    .footer-note {{
      text-align: center;
      font-size: 12px;
      color: #94a3b8;
      margin-top: 36px;
      border-top: 1px solid #f1f5f9;
      padding-top: 20px;
    }}
    @media print {{
      body {{ background: white; padding: 0; }}
      .action-bar {{ display: none !important; }}
      .invoice-card {{ border: none; box-shadow: none; padding: 20px; }}
    }}
    @media (max-width: 640px) {{
      .invoice-card {{ padding: 24px 18px; }}
      .header-row {{ flex-direction: column; gap: 16px; }}
      .inv-details {{ text-align: left; }}
      .bill-section {{ grid-template-columns: 1fr; gap: 16px; }}
      .payment-box {{ grid-template-columns: 1fr; }}
      .summary-box {{ width: 100%; }}
    }}
  </style>
</head>
<body>

  <!-- Top Controls (Hidden during Print / PDF Export) -->
  <div class="action-bar">
    <a href="/" class="btn btn-secondary">
      &larr; Back to Dashboard
    </a>
    <div style="display:flex;gap:8px;">
      <button onclick="window.print()" class="btn btn-primary">
        🖨️ Print / Save as PDF
      </button>
    </div>
  </div>

  <!-- Professional Printable Invoice Document -->
  <div class="invoice-card" id="invoice">
    
    <!-- Top Header -->
    <div class="header-row">
      <div>
        <h1 class="company-title">{account_title or "Payment Services"}</h1>
        <p class="company-sub">Billing & Account Settlement</p>
        <p class="company-sub">Helpline / Support: {support_contact or "Direct Message"}</p>
      </div>
      <div class="inv-details">
        <h2 class="inv-title">INVOICE</h2>
        <p class="inv-meta">
          <strong>Invoice #:</strong> {invoice_num}<br>
          <strong>Issue Date:</strong> {today_str}<br>
          <strong>Due Date:</strong> {due_date}<br>
          <span style="display:inline-block;margin-top:6px;">{status_badge}</span>
        </p>
      </div>
    </div>

    <!-- Client & Billing Section -->
    <div class="bill-section">
      <div class="bill-box">
        <h4>BILLED TO</h4>
        <p class="client-name">{client_name}</p>
        <p>WhatsApp / Phone: <strong>{phone}</strong></p>
        <p>Client Reference ID: {client_id}</p>
      </div>
      <div class="bill-box">
        <h4>PAYMENT STATUS</h4>
        <p>Amount Due: <strong>{currency} {formatted_amt}</strong></p>
        <p>Payment Term: Due on {due_date}</p>
        <p>Status: <strong>{'Settled' if is_paid else 'Unpaid / Action Required'}</strong></p>
      </div>
    </div>

    <!-- Line Items Table -->
    <table>
      <thead>
        <tr>
          <th>Description</th>
          <th style="text-align:center;">Qty</th>
          <th style="text-align:right;">Rate</th>
          <th>Amount</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>
            <div class="item-desc">{notes or 'Professional Services'}</div>
            <div class="item-sub">Invoice #{invoice_num} • Reference settlement</div>
          </td>
          <td style="text-align:center;">1</td>
          <td style="text-align:right;">{currency} {formatted_amt}</td>
          <td><strong>{currency} {formatted_amt}</strong></td>
        </tr>
      </tbody>
    </table>

    <!-- Totals Summary -->
    <div class="summary-row">
      <div class="summary-box">
        <div class="summary-line">
          <span>Subtotal:</span>
          <span>{currency} {formatted_amt}</span>
        </div>
        <div class="summary-line">
          <span>Tax / Processing:</span>
          <span>{currency} 0.00</span>
        </div>
        <div class="summary-line total">
          <span>TOTAL DUE:</span>
          <span style="color:#059669;">{currency} {formatted_amt}</span>
        </div>
      </div>
    </div>

    <!-- Remittance & Bank Transfer Instructions -->
    <div class="payment-box">
      <div class="pay-col">
        <h5>Official Remittance Details</h5>
        <div class="pay-item">Bank Name: <strong>{bank_name}</strong></div>
        <div class="pay-item">Account Title: <strong>{account_title}</strong></div>
        <div class="pay-item">Account Number: <strong>{account_number}</strong></div>
      </div>
      <div class="pay-col">
        <h5>Wire / IBAN & Verification</h5>
        <div class="pay-item">IBAN: <strong>{iban or 'N/A'}</strong></div>
        <div class="pay-item">Notice: <strong>Please send payment slip upon completion</strong></div>
        <div class="pay-item">Support: <strong>{support_contact}</strong></div>
      </div>
    </div>

    <div class="footer-note">
      Thank you for your prompt business and cooperation. Please direct all queries to {support_contact or account_title}.
    </div>

  </div>

</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.get("/api/notifications/summary")
def get_notification_summary():
    """Returns aggregated summary data for mobile notification briefings."""
    clients = agent.load_clients()
    pending = 0.0
    due_today_count = 0
    overdue_count = 0
    overdue_amount = 0.0
    due_clients = []
    overdue_clients = []

    today = datetime.date.today()
    for c in clients:
        if c.get("status", "").lower() != "paid":
            amt = float(c.get("amount_due") or 0)
            pending += amt
            should_remind, cat, reason = agent.evaluate_client(c, today)
            if cat == "DUE_TODAY":
                due_today_count += 1
                due_clients.append(c.get("client_name"))
            elif cat == "OVERDUE":
                overdue_count += 1
                overdue_amount += amt
                overdue_clients.append(c.get("client_name"))

    return {
        "pending_amount": pending,
        "due_today_count": due_today_count,
        "due_clients": due_clients,
        "overdue_count": overdue_count,
        "overdue_amount": overdue_amount,
        "overdue_clients": overdue_clients,
        "timestamp": datetime.datetime.now().isoformat()
    }


# -----------------------------------------------------------------------------
# Static Files & Frontend SPA
# -----------------------------------------------------------------------------
@app.get("/sw.js")
def serve_service_worker():
    sw_file = STATIC_DIR / "sw.js"
    if sw_file.exists():
        return FileResponse(
            sw_file,
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Service-Worker-Allowed": "/"
            }
        )
    return HTMLResponse("// SW not found", status_code=404)


@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return HTMLResponse("<h1>Dashboard Loading...</h1>")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# -----------------------------------------------------------------------------
# Autonomous Daily Background Scheduler
# -----------------------------------------------------------------------------
LAST_AUTONOMOUS_DISPATCH_DATE = None

async def autonomous_reminder_scheduler():
    """Background task that runs 24/7 and automatically dispatches daily reminders at 9:00 AM."""
    global LAST_AUTONOMOUS_DISPATCH_DATE
    print("[AutoScheduler] Autonomous reminder background scheduler initialized.")
    while True:
        try:
            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # Automatically dispatch when 9:00 AM or later and hasn't dispatched today
            if now.hour >= 9 and LAST_AUTONOMOUS_DISPATCH_DATE != today_str:
                bridge_url = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")
                try:
                    res = requests.get(f"{bridge_url}/status", timeout=3)
                    if res.ok and res.json().get("ready"):
                        print(f"[{now.isoformat()}] [AutoScheduler] Running autonomous reminder dispatch...")
                        results = agent.process_reminders(dry_run=False, attach_pdf=True)
                        LAST_AUTONOMOUS_DISPATCH_DATE = today_str
                        reminded = sum(1 for r in results if r["action"] == "REMINDED")
                        print(f"[{now.isoformat()}] [AutoScheduler] Dispatched {reminded} automated reminders.")
                except Exception as ex:
                    print(f"[AutoScheduler] WhatsApp bridge not ready for dispatch: {ex}")
        except Exception as e:
            print(f"[AutoScheduler] Scheduler loop exception: {e}")

        # Sleep for 15 minutes between checks
        await asyncio.sleep(900)

@app.on_event("startup")
async def start_autonomous_scheduler():
    asyncio.create_task(autonomous_reminder_scheduler())

