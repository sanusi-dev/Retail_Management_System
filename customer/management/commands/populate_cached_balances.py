from django.core.management.base import BaseCommand
from customer.models import DepositAccount
from django.db import transaction


class Command(BaseCommand):
    help = "Populate cached balances for all deposit accounts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of accounts to process in each batch",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]

        accounts = DepositAccount.objects.all()
        total = accounts.count()

        self.stdout.write(f"Found {total} deposit accounts to update...")

        updated = 0
        errors = 0

        for account in accounts.iterator(chunk_size=batch_size):
            try:
                with transaction.atomic():
                    account.update_cached_balances()
                    updated += 1

                    if updated % 10 == 0:
                        self.stdout.write(
                            f"Progress: {updated}/{total} "
                            f"({(updated/total*100):.1f}%)"
                        )
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Error updating account {account.account_number}: {e}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(f"\nCompleted! Updated: {updated}, Errors: {errors}")
        )
