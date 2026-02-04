from django.core.management.base import BaseCommand
from customer.models import DepositAccount
from decimal import Decimal


class Command(BaseCommand):
    help = "Verify that cached balances match calculated balances"

    def handle(self, *args, **options):
        accounts = DepositAccount.objects.all()
        total = accounts.count()

        self.stdout.write(f"Verifying {total} deposit accounts...")

        mismatches = 0

        for i, account in enumerate(accounts, 1):
            # Calculate fresh values
            calc_total = account._calculate_total_balance()
            calc_allocated = account._calculate_allocated_balance()
            calc_available = account._calculate_available_balance()

            # Compare with cached
            if account.cached_total_balance != calc_total:
                self.stdout.write(
                    self.style.WARNING(
                        f"MISMATCH {account.account_number} - Total: "
                        f"Cached={account.cached_total_balance}, "
                        f"Calculated={calc_total}"
                    )
                )
                mismatches += 1

            if account.cached_allocated_balance != calc_allocated:
                self.stdout.write(
                    self.style.WARNING(
                        f"MISMATCH {account.account_number} - Allocated: "
                        f"Cached={account.cached_allocated_balance}, "
                        f"Calculated={calc_allocated}"
                    )
                )
                mismatches += 1

            if account.cached_available_balance != calc_available:
                self.stdout.write(
                    self.style.WARNING(
                        f"MISMATCH {account.account_number} - Available: "
                        f"Cached={account.cached_available_balance}, "
                        f"Calculated={calc_available}"
                    )
                )
                mismatches += 1

            if i % 50 == 0:
                self.stdout.write(f"Checked {i}/{total}...")

        if mismatches == 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ All {total} accounts verified successfully!")
            )
        else:
            self.stdout.write(self.style.ERROR(f"✗ Found {mismatches} mismatches"))
