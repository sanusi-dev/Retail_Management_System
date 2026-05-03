# Date Backdating Implementation Guide

## What This Is

Several modal forms in this codebase have a date picker field that lets staff
backdate a record — for example, logging a deposit that physically happened two
days ago. The `date` input is a plain HTML field, not part of the Django form
class, so it is read from `request.POST` directly in the view.

The current implementation has a bug: it uses `datetime.strptime(date_str, "%Y-%m-%d")`
which produces a datetime with time `00:00:00`, discarding the actual time the
record was created. Since the model uses a `DateTimeField`, this makes every
backdated record appear to have happened at midnight, which is wrong.

This guide describes the correct implementation across all three layers: the
service function, the view, and the template.

---

## The Correct Date Handling Logic

When the user picks a date from the date picker, the intent is:
**"This happened on that date, at approximately the time I am logging it now."**

So the correct approach is: take the current time in the project timezone
(`Africa/Lagos`), and replace only the date portion with what the user selected.
The time component is preserved from `timezone.now()`.

```python
from django.utils import timezone

def parse_backdate(date_str):
    """
    Parse a date string (YYYY-MM-DD) from a form input and return a timezone-aware
    datetime that uses the user-selected date but the current local time.
    Returns None if date_str is empty or invalid.
    """
    if not date_str:
        return None
    try:
        from datetime import datetime
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        now = timezone.localtime(timezone.now())
        return now.replace(year=parsed.year, month=parsed.month, day=parsed.day)
    except (ValueError, TypeError):
        return None
```

Place this helper function at the top of `customer/views.py` (or in
`customer/utils.py` if a utils module exists). It is used by every view that
has a date field.

---

## Layer 1 — The Service Function

The service function must accept an optional `created_at` parameter and apply
it after creating the record, in a single additional `.save()` call if provided.

Apply this pattern to the following service functions in `customer/services.py`:
- `record_deposit`
- `record_withdrawal` (if it exists and has a date field in its modal)
- `record_cfa_fulfillment` (for the CFA disbursement modal)

### Pattern:

```python
def record_deposit(account, amount, note, user, request=None, created_at=None):
    # ... existing validation and balance logic unchanged ...

    txn = Transaction.objects.create(
        account=account,
        amount=amount,
        note=note,
        created_by=user,
        transaction_type=Transaction.Type.DEPOSIT,
    )

    # Apply backdated datetime if provided — replaces only the date,
    # time component comes from when the record was logged (see view).
    if created_at is not None:
        txn.created_at = created_at
        txn.save(update_fields=["created_at"])

    # ... existing balance refresh and audit log calls unchanged ...
    return txn
```

**Rules:**
- `created_at=None` is the default — existing callers are unaffected
- The `if created_at is not None` guard means passing `None` explicitly is safe
- `update_fields=["created_at"]` ensures only that field is written in the second save
- The service must return the `txn` object so the view can pass `created_at` to it

---

## Layer 2 — The View

The view parses the date string using `parse_backdate()` and passes the result
directly to the service. There is no post-save patching.

### Pattern (using `modal_deposit` as the reference):

```python
from django.utils import timezone
from datetime import datetime

def parse_backdate(date_str):
    if not date_str:
        return None
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        now = timezone.localtime(timezone.now())
        return now.replace(year=parsed.year, month=parsed.month, day=parsed.day)
    except (ValueError, TypeError):
        return None


def modal_deposit(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related("deposit_account"), pk=pk
    )

    if request.method == "POST":
        form = TransactionForm(request.POST)
        if form.is_valid():
            try:
                custom_date = parse_backdate(request.POST.get("date"))

                txn = customer_services.record_deposit(
                    account=customer.deposit_account,
                    amount=form.cleaned_data["amount"],
                    note=form.cleaned_data.get("note", ""),
                    user=request.user,
                    request=request,
                    created_at=custom_date,        # None if user left default date
                )
                messages.success(
                    request,
                    f"Deposit of ₦{form.cleaned_data['amount']:,.0f} recorded for {customer.full_name}.",
                )
                response = HttpResponse(status=204)
                response["HX-Trigger"] = "customerDetailChanged"
                return response

            except (ValidationError, customer_services.BusinessRuleViolation) as e:
                form.add_error(None, str(e))
    else:
        form = TransactionForm()

    return render(request, "customers/modals/deposit_modal.html", {
        "customer": customer,
        "form": form,
    })
```

**What changed from the broken version:**
- `parse_backdate()` is called once, before the service call
- The result is passed directly into the service as `created_at=`
- There is no second `.save()` call in the view — the service owns it
- `datetime.strptime(..., "%Y-%m-%d")` is never called directly in the view
- The time component is always preserved from `timezone.now()`

---

## Layer 3 — The Template

The date field is a plain HTML `<input type="date">` outside the Django form
fields. It must:
- Default to today's date using Django's `{% now %}` tag
- Use `name="date"` so `request.POST.get("date")` finds it
- Not be inside the Django form class (it is intentionally a raw POST field)

```html
<div>
  <label class="field-label">Date</label>
  <input type="date"
         name="date"
         class="field-input"
         value="{% now 'Y-m-d' %}">
</div>
```

No changes needed to this field if it already exists in the template.
If it does not exist, add it between the amount field and the note field.

---

## Which Modals Require This

| Modal | Date field | Action required |
|---|---|---|
| Record Deposit | Yes — already exists | Update service to accept `created_at` |
| Record Withdrawal | Yes — already exists | Update service to accept `created_at` |
| Record CFA Disbursement | Yes — already exists | Update service to accept `created_at` |
| New CFA Agreement | Must be added | Add date input to template + update service to accept `created_at` |
| Edit CFA Agreement | Must be added | Add date input to template + update service to accept `created_at` |
| Cancel CFA Agreement | No — not applicable | Cancel records current moment only, no date input |
| Void CFA Disbursement | No — not applicable | Void records current moment only, no date input |
| Void Transaction | No — not applicable | Void records current moment only, no date input |

For any modal marked **"Must be added"**, add this field to the template between
the last data field and the note/reason field:

```html
<div>
  <label class="field-label">Date</label>
  <input type="date"
         name="date"
         class="field-input"
         value="{% now 'Y-m-d' %}">
</div>
```

---

## Verification

After implementing, verify the following:

1. **Time is preserved on backdating:**
   Record a deposit, choose yesterday's date. Check the transaction's `created_at`
   in Django admin or shell — it must show yesterday's date with today's approximate
   time, not `00:00:00`.

2. **Default date works:**
   Open the modal without changing the date. Submit. The transaction's `created_at`
   must be today's date and approximately the current time.

3. **Invalid date is handled gracefully:**
   If `parse_backdate` receives a malformed string, it returns `None` and the
   service uses the auto-generated `created_at` from `Transaction.objects.create()`.
   No exception should surface to the user.

4. **No double save without a custom date:**
   If the user does not change the date field (it stays as today), `parse_backdate`
   still returns a value (today's date with current time). This is fine — it writes
   the same date with slightly more precision. If you want to skip the second save
   entirely when the date matches today, compare the date portion:

   ```python
   today = timezone.localtime(timezone.now()).date()
   parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
   custom_date = parse_backdate(date_str) if parsed_date != today else None
   ```

   This optimisation is optional. The default behaviour (always passing the parsed
   date) is correct and harmless.