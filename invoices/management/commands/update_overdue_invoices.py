"""
Run daily (via cron / Windows Task Scheduler / celery-beat) to flip
PENDING/PARTIALLY_PAID invoices past their due_date to OVERDUE:

    python manage.py update_overdue_invoices
"""
from django.core.management.base import BaseCommand
from invoices.services import mark_overdue_invoices


class Command(BaseCommand):
    help = "Marks invoices past their due_date as OVERDUE."

    def handle(self, *args, **options):
        count = mark_overdue_invoices()
        self.stdout.write(self.style.SUCCESS(f"Updated {count} invoice(s) to OVERDUE status."))