import argparse
import sys
from datetime import date
from agent import PaymentReminderAgent
from dispatcher import get_dispatcher
import config

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def print_banner():
    print("""
================================================================
          AUTONOMOUS PAYMENT REMINDER AGENT
================================================================
    """)


def print_summary_table(results):
    print("\n" + "=" * 80)
    print(f"{'CLIENT ID':<10} | {'CLIENT NAME':<22} | {'ACTION':<10} | {'CATEGORY':<12} | {'DETAILS'}")
    print("-" * 80)
    for r in results:
        status_symbol = "[+]" if r["action"] == "REMINDED" else "[-]"
        print(f"{r['client_id']:<10} | {r['name'][:20]:<22} | {status_symbol} {r['action']:<6} | {r['category']:<12} | {r['reason']}")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Autonomous Payment Reminder Agent Runner")
    parser.add_argument("--dry-run", action="store_true", help="Preview reminders without sending or modifying data")
    parser.add_argument("--client", type=str, default=None, help="Process only a specific client ID (e.g., CLI-001)")
    parser.add_argument("--channel", type=str, default=None, help="Override dispatcher channel (simulation, email_to_sms, telegram, twilio)")
    parser.add_argument("--no-pdf", action="store_true", help="Send text-only messages without generating and attaching PDF invoices")
    args = parser.parse_args()

    attach_pdf = not args.no_pdf

    print_banner()
    print(f"[*] Execution Date : {date.today()}")
    print(f"[*] Dispatcher Mode: {args.channel or config.DISPATCHER_MODE}")
    print(f"[*] Dry Run Mode   : {args.dry_run}")
    print(f"[*] Attach PDF     : {attach_pdf}")
    print(f"[*] Bank Configured: {config.PAYMENT_DETAILS['bank_name']} ({config.PAYMENT_DETAILS['account_title']})")

    dispatcher = get_dispatcher(args.channel)
    agent = PaymentReminderAgent(dispatcher=dispatcher)

    results = agent.process_reminders(dry_run=args.dry_run, target_client_id=args.client, attach_pdf=attach_pdf)
    print_summary_table(results)

    reminded_count = sum(1 for r in results if r["action"] == "REMINDED")
    skipped_count = sum(1 for r in results if r["action"] == "SKIPPED")
    print(f"Summary: {reminded_count} reminder(s) generated/sent, {skipped_count} skipped.")


if __name__ == "__main__":
    main()
