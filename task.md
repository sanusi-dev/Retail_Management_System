# HTMX Modal & Middleware Migration Guide

**Purpose:** Replace the current over-engineered modal/toast implementation with a clean,
minimal one. This guide is written for an AI coding agent to execute independently.

---

## 1. What Is Changing and Why

### Current (broken) implementation

| Layer | Problem |
|---|---|
| `HtmxMessageMiddleware` | Uses `MiddlewareMixin` (legacy), checks `content_type` to decide whether to process, which means success responses must manually set `content_type="text/html"` or the toast silently breaks |
| Modal views | Split into two views per modal: one `@require_GET` loader and one `_submit` handler, connected by two separate URLs |
| `_modal_success_response()` | A shared helper that re-renders the entire customer detail partial, decodes it from bytes, sets 3 custom headers, and returns it — duplicating all the query logic from `customer_detail` |
| `_customer_detail_context()` | A second copy of the context-building logic that must be kept in sync with `customer_detail` manually |
| `closeModal` JS | A global function called by `onclick="closeModal()"` scattered across templates, plus a redundant `document.addEventListener('closeModal', ...)` that fires the same function from `HX-Trigger` |
| `HX-Trigger` in views | Views manually build `json.dumps({"depositSuccess": True})` alongside messages, forcing the middleware to merge them — error-prone and unnecessary |

### Target (clean) implementation

- **One middleware**, using the modern `__init__`/`__call__` pattern, with no content-type
  filtering. It intercepts all non-redirect HTMX responses and serialises Django messages into
  `HX-Trigger: {"messages": [...]}` automatically.
- **One view per modal operation**, handling both GET and POST.
- **One URL per modal operation**.
- **Success response is just `HttpResponse()`** — empty body, no custom headers. HTMX uses
  the form's declared `hx-target`/`hx-swap` to clear the modal, middleware attaches the toast.
- **No `_modal_success_response()` helper** — delete it entirely.
- **No `_customer_detail_context()` helper** — delete it entirely.
- **No `closeModal()` global JS function** — modal close is handled inline via
  `htmx.find('#modal_container').innerHTML = ''` or by the empty swap on success.
- **No `HX-Trigger` header set manually in any view** — the middleware owns that entirely.

---

## 2. Order of Operations

Execute in this exact order. Each step depends on the previous.

```
Step 1 → Replace the middleware
Step 2 → Update main.js
Step 3 → Delete dead helpers from views.py
Step 4 → Rewrite each modal view (GET+POST merged, one URL)
Step 5 → Update each modal template
Step 6 → Clean up URL patterns
Step 7 → Verify
```

---

## 3. Step 1 — Replace the Middleware

### 3.1 Locate the middleware file

Find the file containing `HtmxMessageMiddleware`. It will look like one of:
- `core/middleware.py`
- `middleware.py`
- `common/middleware.py`

### 3.2 Delete the entire existing class

Remove everything from `class HtmxMessageMiddleware` to the end of the class, including all
imports that are exclusively used by it (`MiddlewareMixin`, `LEVEL_TAGS`).

### 3.3 Write the replacement class

Paste this exactly into the file:

```python
import json
from django.contrib.messages import get_messages


class HtmxMessageMiddleware:
    """
    Intercepts Django messages on HTMX responses and serialises them into
    HX-Trigger as a 'messages' event. The frontend showMessages listener
    (in main.js) picks this up and calls SweetAlert2.

    Skips redirects because the browser follows them transparently and
    HTMX never sees the headers — messages must stay in the session.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if "HX-Request" not in request.headers:
            return response

        if 300 <= response.status_code < 400:
            return response

        storage = get_messages(request)
        message_list = [
            {"message": str(msg), "tags": msg.tags}
            for msg in storage
        ]

        if not message_list:
            return response

        existing = response.get("HX-Trigger")
        if existing:
            try:
                trigger_data = json.loads(existing)
            except (json.JSONDecodeError, ValueError):
                trigger_data = {existing: True}
        else:
            trigger_data = {}

        trigger_data["messages"] = message_list
        response["HX-Trigger"] = json.dumps(trigger_data)

        return response
```

### 3.4 Verify `settings.py`

Check `MIDDLEWARE` in `settings.py`. The entry must point to this class. It should look like:

```python
"your_app.middleware.HtmxMessageMiddleware",
```

No change needed if the import path is already correct.

---

## 4. Step 2 — Update `main.js`

### 4.1 Find the toast listener

Locate the block that begins with:

```js
document.addEventListener('showMessages', function(e) {
```

### 4.2 Replace it

The old middleware serialised messages under `showMessages` with a field called `text` and
`icon`. The new middleware uses `messages` as the event name, with fields `message` and `tags`.
Replace the entire listener block with:

```js
// ── SweetAlert2 toast system ──────────────────────────────────────────────────

document.addEventListener('messages', function (e) {
  const msgs = Array.isArray(e.detail) ? e.detail : e.detail?.value;
  if (!msgs || msgs.length === 0) return;
  let queue = Promise.resolve();
  msgs.forEach(function (msg) {
    queue = queue.then(function () {
      return Swal.fire(buildSwalConfig(msg));
    });
  });
});

function buildSwalConfig(msg) {
  // tags from Django can be 'success', 'error', 'warning', 'info', 'debug'
  const tag = (msg.tags || 'info').split(' ').pop();
  const icon = { debug: 'info', info: 'info', success: 'success', warning: 'warning', error: 'error' }[tag] || 'info';
  const isError = icon === 'error';
  return {
    text:              msg.message,
    icon:              icon,
    toast:             true,
    position:          'top-end',
    showConfirmButton: false,
    timer:             isError ? 0 : 4000,
    timerProgressBar:  !isError,
    showCloseButton:   true,
    customClass: { popup: 'swal-rms-popup' },
    didOpen: function (popup) {
      popup.addEventListener('mouseenter', Swal.stopTimer);
      popup.addEventListener('mouseleave', Swal.resumeTimer);
    },
  };
}
```

### 4.3 Find and delete the `closeModal` function and its event listener

Remove these blocks entirely:

```js
function closeModal() {
  const container = document.getElementById('modal_container');
  if (container) container.innerHTML = '';
}

document.addEventListener('closeModal', function() {
  closeModal();
});
```

Replace the Escape key handler to work without the function:

```js
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    const container = document.getElementById('modal_container');
    if (container) container.innerHTML = '';
  }
});
```

### 4.4 Find and delete the `showMessages` function

Remove the standalone function:

```js
function showMessages(messages) {
  if (!messages || messages.length === 0) return;
  ...
}
```

If any base template calls `showMessages(...)` inline via a `<script>` tag on full page load
(to handle non-HTMX messages), replace that call with direct inline SweetAlert2 calls instead,
or handle it by rendering messages in the base template HTML for non-HTMX requests.

---

## 5. Step 3 — Delete Dead Helpers from Views

Find the file(s) containing these two helpers and delete them completely:

### 5.1 Delete `_modal_success_response`

```python
# DELETE THIS ENTIRE FUNCTION
def _modal_success_response(request, customer, active_tab="transactions"):
    ...
```

### 5.2 Delete `_customer_detail_context`

```python
# DELETE THIS ENTIRE FUNCTION
def _customer_detail_context(customer, active_tab="transactions"):
    ...
```

After deletion, do a project-wide search for any call sites:

```
grep -rn "_modal_success_response\|_customer_detail_context" .
```

If any calls remain, they will be removed in Step 4 when the modal views are rewritten.

---

## 6. Step 4 — Rewrite Each Modal View

For every modal operation in the codebase, apply this pattern. The examples below use
`modal_deposit` — apply the same structure to `modal_withdrawal`, `modal_cfa_agreement`,
and any other modal views.

### 6.1 Pattern — one view, GET + POST

```python
from django.http import HttpResponse

def modal_deposit(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related("deposit_account"), pk=pk
    )
    form = TransactionForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            try:
                txn = customer_services.record_deposit(
                    account=customer.deposit_account,
                    amount=form.cleaned_data["amount"],
                    note=form.cleaned_data.get("note", ""),
                    user=request.user,
                    request=request,
                )
                date_str = request.POST.get("date")
                if date_str:
                    try:
                        txn.created_at = datetime.strptime(date_str, "%Y-%m-%d")
                        txn.save(update_fields=["created_at"])
                    except (ValueError, TypeError):
                        pass

                messages.success(
                    request,
                    f"Deposit of ₦{form.cleaned_data['amount']:,.0f} recorded for {customer.full_name}.",
                )
                # Empty response — HTMX clears modal via hx-target/hx-swap on the form.
                # Middleware attaches HX-Trigger: {"messages": [...]} automatically.
                return HttpResponse()

            except (ValidationError, customer_services.BusinessRuleViolation) as e:
                form.add_error(None, str(e))
                # Fall through to re-render form below

        # Invalid form — re-render modal with errors
        # Middleware will attach any messages.error() calls if present
        context = {"customer": customer, "form": form}
        return render(request, "customers/modals/deposit_modal.html", context)

    # GET — render empty form
    context = {"customer": customer, "form": form}
    return render(request, "customers/modals/deposit_modal.html", context)
```

### 6.2 All 8 modal operations — explicit migration table

Every row below represents one modal operation. For each one: merge the split views into a
single view, reduce to one URL, and apply the standard pattern. The table gives you the
exact view names, URL names, form classes, template paths, and the correct success message
to use in `messages.success(...)`.

| # | Modal | Current view names to merge | Merged view name | URL name | Form class | Template path | Success message |
|---|---|---|---|---|---|---|---|
| 1 | Record Deposit | `modal_deposit` + `modal_deposit_submit` | `modal_deposit` | `modal_deposit` | `TransactionForm` | `customers/modals/deposit_modal.html` | `"Deposit of ₦{amount:,.0f} recorded for {customer.full_name}."` |
| 2 | Record Withdrawal | `modal_withdrawal` + `modal_withdrawal_submit` | `modal_withdrawal` | `modal_withdrawal` | `TransactionForm` | `customers/modals/withdrawal_modal.html` | `"Withdrawal of ₦{amount:,.0f} recorded for {customer.full_name}."` |
| 3 | New CFA Agreement | `modal_cfa_agreement` + `modal_cfa_agreement_submit` | `modal_cfa_agreement` | `modal_cfa_agreement` | `CfaAgreementForm` | `customers/modals/cfa_agreement_modal.html` | `"CFA agreement created for {customer.full_name}."` |
| 4 | Edit CFA Agreement | `modal_edit_cfa` + `modal_edit_cfa_submit` | `modal_edit_cfa` | `modal_edit_cfa` | `CfaAgreementForm` | `customers/modals/edit_cfa_modal.html` | `"CFA agreement updated."` |
| 5 | Cancel CFA Agreement | `modal_cancel_cfa` + `modal_cancel_cfa_submit` | `modal_cancel_cfa` | `modal_cancel_cfa` | `CancelCfaForm` | `customers/modals/cancel_cfa_modal.html` | `"CFA agreement cancelled."` |
| 6 | Record CFA Disbursement | `modal_cfa_disbursement` + `modal_cfa_disbursement_submit` | `modal_cfa_disbursement` | `modal_cfa_disbursement` | `CfaDisbursementForm` | `customers/modals/cfa_disbursement_modal.html` | `"Disbursement recorded."` |
| 7 | Void CFA Disbursement | `modal_void_cfa_disbursement` + `modal_void_cfa_disbursement_submit` | `modal_void_cfa_disbursement` | `modal_void_cfa_disbursement` | `VoidReasonForm` | `customers/modals/void_cfa_disbursement_modal.html` | `"Disbursement voided."` |
| 8 | Void Transaction | `modal_void_transaction` + `modal_void_transaction_submit` | `modal_void_transaction` | `modal_void_transaction` | `VoidReasonForm` | `customers/modals/void_transaction_modal.html` | `"Transaction voided."` |

**Important notes per operation:**

**#1 Record Deposit** — has a custom date field outside the Django form (`request.POST.get("date")`).
Keep that post-save logic in the merged view exactly as shown in the pattern above.

**#2 Record Withdrawal** — same structure as deposit. Check whether the service call is
`customer_services.record_withdrawal(...)` and mirror the date field handling if present.

**#3 New CFA Agreement** — template includes the live XOF preview (`updateCfaPreview` JS).
Do not remove the JS hook. The view itself needs no changes for the preview — it is purely
client-side. The `cfa-available-balance` data attribute on the template must remain.

**#4 Edit CFA Agreement** — this view receives a CFA agreement `pk`, not a customer `pk`.
The URL pattern will be `modal/cfa/<uuid:pk>/edit`. The form must be pre-populated:
`form = CfaAgreementForm(request.POST or None, instance=cfa_agreement)`.

**#5 Cancel CFA Agreement** — this is a danger action. The modal template likely has a
warning UI. Keep the template as-is; only the view/URL structure changes. The form may be
minimal (just a confirmation or reason field). On success: `messages.warning(request, ...)` 
is more appropriate than `messages.success` for a destructive action.

**#6 Record CFA Disbursement** — receives a CFA agreement `pk`. Has a date field like
deposit — apply the same `request.POST.get("date")` / `txn.created_at` pattern if present.

**#7 Void CFA Disbursement** — receives a disbursement `pk`. Form likely only has a `reason`
field. No date handling needed. Service call voids the specific disbursement record.

**#8 Void Transaction** — receives a transaction `pk`. Same structure as #7. Service call
voids the specific transaction record.

### 6.3 Standard pattern rules (apply to all 8)

- `form = TheForm(request.POST or None)` at the top (or `instance=obj` for edit operations)
- On valid POST success → `messages.success(...)` then `return HttpResponse()`
- On invalid POST or service exception → `form.add_error(None, str(e))` then re-render modal
- On GET → render the modal template with empty (or pre-populated) form
- Never call `_modal_success_response()` — it will not exist after Step 3

### 6.4 Remove the `@require_GET` decorator

The old GET-only loader views had `@require_GET`. The merged view handles both methods,
so this decorator must be removed from all 8 views. Do not add `@require_POST` to anything.

---

## 7. Step 5 — Update Each Modal Template

For every modal template apply these changes:

### 7.1 Replace `onclick="closeModal()"` with inline HTMX

Find every occurrence of `onclick="closeModal()"` and replace with:

```html
hx-on:click="document.getElementById('modal_container').innerHTML = ''"
```

For the backdrop click-to-close pattern, replace:

```html
onclick="if(event.target===this) closeModal()"
```

with:

```html
hx-on:click="if(event.target===this) document.getElementById('modal_container').innerHTML = ''"
```

### 7.2 Verify the form attributes

The form tag must declare both target and swap explicitly:

```html
<form hx-post="{% url 'modal_deposit' customer.pk %}"
      hx-target="#modal_container"
      hx-swap="innerHTML">
```

`hx-target="#modal_container"` and `hx-swap="innerHTML"` are required. On success, the empty
response body is swapped in, clearing the modal. On error, the re-rendered modal HTML replaces
the current modal content.

### 7.3 Add non-field error display

Since validation errors from `form.add_error(None, ...)` go into `non_field_errors`, every
modal form needs this block above the fields:

```html
{% if form.non_field_errors %}
  <div class="text-xs text-rose-600 bg-rose-50 rounded-lg px-3 py-2 mb-4">
    {% for error in form.non_field_errors %}{{ error }}{% endfor %}
  </div>
{% endif %}
```

### 7.4 Remove hidden `transaction_type` field if unused

The old templates had:

```html
<input type="hidden" name="transaction_type" value="deposit">
```

If the merged view no longer reads this from `request.POST` directly (it shouldn't — the form
type is determined by which URL was called), remove this hidden field.

---

## 8. Step 6 — Clean Up URL Patterns

For every modal that previously had two URLs, reduce to one.

### Before

```python
path("modal/deposit/<uuid:pk>", modal_deposit, name="modal_deposit"),
path("modal/deposit/<uuid:pk>/submit", modal_deposit_submit, name="modal_deposit_submit"),
```

### After

```python
path("modal/deposit/<uuid:pk>", modal_deposit, name="modal_deposit"),
```

Apply this reduction to all 8 modal URL pairs. The complete before/after for every URL:

```python
# BEFORE — 16 paths (8 loaders + 8 submit handlers)
path("modal/deposit/<uuid:pk>", modal_deposit, name="modal_deposit"),
path("modal/deposit/<uuid:pk>/submit", modal_deposit_submit, name="modal_deposit_submit"),
path("modal/withdrawal/<uuid:pk>", modal_withdrawal, name="modal_withdrawal"),
path("modal/withdrawal/<uuid:pk>/submit", modal_withdrawal_submit, name="modal_withdrawal_submit"),
path("modal/cfa/<uuid:pk>", modal_cfa_agreement, name="modal_cfa_agreement"),
path("modal/cfa/<uuid:pk>/submit", modal_cfa_agreement_submit, name="modal_cfa_agreement_submit"),
path("modal/cfa/<uuid:pk>/edit", modal_edit_cfa, name="modal_edit_cfa"),
path("modal/cfa/<uuid:pk>/edit/submit", modal_edit_cfa_submit, name="modal_edit_cfa_submit"),
path("modal/cfa/<uuid:pk>/cancel", modal_cancel_cfa, name="modal_cancel_cfa"),
path("modal/cfa/<uuid:pk>/cancel/submit", modal_cancel_cfa_submit, name="modal_cancel_cfa_submit"),
path("modal/cfa/<uuid:pk>/disbursement", modal_cfa_disbursement, name="modal_cfa_disbursement"),
path("modal/cfa/<uuid:pk>/disbursement/submit", modal_cfa_disbursement_submit, name="modal_cfa_disbursement_submit"),
path("modal/disbursement/<uuid:pk>/void", modal_void_cfa_disbursement, name="modal_void_cfa_disbursement"),
path("modal/disbursement/<uuid:pk>/void/submit", modal_void_cfa_disbursement_submit, name="modal_void_cfa_disbursement_submit"),
path("modal/transaction/<uuid:pk>/void", modal_void_transaction, name="modal_void_transaction"),
path("modal/transaction/<uuid:pk>/void/submit", modal_void_transaction_submit, name="modal_void_transaction_submit"),

# AFTER — 8 paths only
path("modal/deposit/<uuid:pk>", modal_deposit, name="modal_deposit"),
path("modal/withdrawal/<uuid:pk>", modal_withdrawal, name="modal_withdrawal"),
path("modal/cfa/<uuid:pk>", modal_cfa_agreement, name="modal_cfa_agreement"),
path("modal/cfa/<uuid:pk>/edit", modal_edit_cfa, name="modal_edit_cfa"),
path("modal/cfa/<uuid:pk>/cancel", modal_cancel_cfa, name="modal_cancel_cfa"),
path("modal/cfa/<uuid:pk>/disbursement", modal_cfa_disbursement, name="modal_cfa_disbursement"),
path("modal/disbursement/<uuid:pk>/void", modal_void_cfa_disbursement, name="modal_void_cfa_disbursement"),
path("modal/transaction/<uuid:pk>/void", modal_void_transaction, name="modal_void_transaction"),
```

The exact URL path strings above may differ from your codebase — match what already exists.
The rule is: one path per modal, zero `/submit` variants.

After removing the submit URLs, confirm no template still references the old submit URL names:

```bash
grep -rn "_submit" templates/
```

Zero results required. Any hit means a template `hx-post` still points to a deleted URL —
update it to use the merged view's URL name.

---

## 9. Step 7 — Verification Checklist

Work through each item in order. Each must pass before marking the migration complete.

### 9.1 Middleware

- [ ] `HtmxMessageMiddleware` uses `__init__`/`__call__`, not `MiddlewareMixin`
- [ ] No `content_type` check anywhere in the middleware
- [ ] Redirects (`300–399`) are skipped
- [ ] Non-HTMX requests (`HX-Request` absent) are skipped
- [ ] Messages are serialised as `{"messages": [{"message": "...", "tags": "..."}]}`
- [ ] Existing `HX-Trigger` header is merged, not overwritten

### 9.2 JavaScript

- [ ] No `closeModal` function defined anywhere in JS files
- [ ] No `document.addEventListener('closeModal', ...)` listener
- [ ] No `showMessages` standalone function
- [ ] `document.addEventListener('messages', ...)` listener exists and reads `msg.message`
      and `msg.tags`
- [ ] Escape key handler clears `#modal_container` directly without calling `closeModal`

### 9.3 Views

- [ ] `_modal_success_response` does not exist anywhere in the codebase
- [ ] `_customer_detail_context` does not exist anywhere in the codebase
- [ ] No modal view is decorated with `@require_GET`
- [ ] Every modal view handles both GET and POST
- [ ] Every successful POST returns `HttpResponse()` with no custom headers
- [ ] Every failed POST re-renders the modal template with the form

### 9.4 Templates

- [ ] No template contains `onclick="closeModal()"`
- [ ] Every modal form has `hx-target="#modal_container"` and `hx-swap="innerHTML"`
- [ ] Every modal form posts to a single URL (no `_submit` suffix URLs)
- [ ] Every modal template displays `form.non_field_errors`

### 9.5 URLs

- [ ] No URL pattern ends with `/submit`
- [ ] `grep -rn "modal_deposit_submit\|modal_withdrawal_submit"` returns zero results

### 9.6 End-to-end manual test — run for each of the 8 modals

| # | Modal | Open from |
|---|---|---|
| 1 | Record Deposit | Customer detail → Deposit button |
| 2 | Record Withdrawal | Customer detail → Withdraw button |
| 3 | New CFA Agreement | Customer detail → New CFA button / CFA tab empty state |
| 4 | Edit CFA Agreement | CFA tab → Edit button on active/partially fulfilled agreement |
| 5 | Cancel CFA Agreement | CFA tab → Cancel button |
| 6 | Record CFA Disbursement | CFA tab → Record Disbursement button |
| 7 | Void CFA Disbursement | CFA tab → Void button on disbursement row |
| 8 | Void Transaction | Transactions tab → Void button on transaction row |

Checks for each modal:

1. Trigger button opens the modal ✓
2. Submit with invalid/empty required field — modal stays open, inline error shown ✓
3. Submit with valid data — modal closes, SweetAlert2 toast appears top-right ✓
4. Press Escape with modal open — modal closes ✓
5. Click the backdrop — modal closes ✓
6. Click the × button — modal closes ✓
7. After successful submit, the underlying page data reflects the change on reload ✓

---

## 10. What Must Not Exist After Migration

Do a final grep sweep. Each of these must return zero results:

```bash
grep -rn "closeModal"                  # templates and JS
grep -rn "_modal_success_response"     # views
grep -rn "_customer_detail_context"    # views
grep -rn "modal_deposit_submit"        # urls and templates
grep -rn "modal_withdrawal_submit"     # urls and templates
grep -rn "MiddlewareMixin"             # middleware
grep -rn "content_type.*text/html"     # HttpResponse calls in modal views
grep -rn "HX-Retarget"                # modal views (should be gone)
grep -rn "HX-Reswap"                  # modal views (should be gone)
grep -rn "showMessages"               # JS (old event name, replaced by 'messages')
```

Any hit is a regression. Fix before considering the migration done.