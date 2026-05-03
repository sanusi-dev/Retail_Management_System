# Task: Reimplement the Modal System

## Context

The current modal implementation is broken and needs to be fully replaced.
This task describes the exact pattern to implement, based on
https://blog.benoitblanchon.fr/django-htmx-modal-form/ adapted for Tailwind CSS
instead of Bootstrap.

Read this entire document before touching any file.
Execute every step in the order given. Do not skip steps.

---

## How the Pattern Works — Read This First

The pattern has three moving parts that work together:

**1. `htmx:afterSwap` → shows the modal**
When HTMX swaps content into `#modal_container`, the JS listener fires and wires
up the close buttons (backdrop click, × button, Cancel button).

**2. `htmx:beforeSwap` → hides the modal on success**
When a form POST returns a 204 with an empty body, HTMX fires `htmx:beforeSwap`
before attempting to swap. The JS listener detects: target is `#modal-dialog` AND
response body is empty → call `closeModal()` and set `shouldSwap = false` to
prevent HTMX from clearing the dialog content while it's still animating away.

**3. Form validation errors stay inside the dialog**
`hx-target="this"` is on `#modal-dialog` (the inner white card), NOT on
`#modal_container`. When the server returns a 200 with validation errors, HTMX
swaps the new form HTML into `#modal-dialog` only — the backdrop stays, the
dialog stays open, only the form content is refreshed.

**The 204 status code is the success signal.**
- 204 + empty body = success → JS closes the modal
- 200 + HTML body = validation error → JS swaps the form content inside the dialog
- The middleware attaches `HX-Trigger: {"messages": [...]}` to the 204 automatically
  so the SweetAlert2 toast fires without any manual header work in the view

**Page refresh after success** uses `HX-Trigger: customerDetailChanged` on the 204
response. The customer detail partial listens for this event and re-fetches itself.
The middleware merges the `messages` key into whatever `HX-Trigger` is already set.

---

## Step 1 — Replace the Middleware

File: `middleware.py` (at project root, next to `mrms/`)

Delete the entire existing `HtmxMessageMiddleware` class and replace it with this
exact implementation. Remove any imports that are no longer used after deletion
(`MiddlewareMixin`, `LEVEL_TAGS`, etc.).

```python
import json
from django.contrib.messages import get_messages


class HtmxMessageMiddleware:
    """
    Intercepts Django messages on HTMX responses and serialises them into
    HX-Trigger as a 'messages' event payload for SweetAlert2.

    Skips redirects (300-399): browser follows them transparently and HTMX
    never sees the headers, so messages must stay in the session.
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

**Verify:** `settings.py` `MIDDLEWARE` list must contain the import path pointing
to this class. It must be last in the list. No other change to `settings.py`.

---

## Step 2 — Update `main.js`

File: `static/js/main.js` (or wherever the project JS entry point is)

### 2a. Delete these blocks entirely — they must not exist after this step:

```js
function closeModal() { ... }
document.addEventListener('closeModal', function() { ... });
document.addEventListener('showMessages', function(e) { ... });
function showMessages(messages) { ... }
function buildSwalConfig(msg) { ... }
```

Also remove the old Escape key handler (it will be replaced below).

### 2b. Add this complete replacement block:

```js
// ── Modal management ──────────────────────────────────────────────────────────

function closeModal() {
  document.getElementById("modal_container").innerHTML = "";
}

// Show modal: fires after HTMX swaps content into #modal_container
htmx.on("htmx:afterSwap", function (e) {
  if (e.detail.target.id === "modal_container") {
    var backdrop = document.getElementById("modal-backdrop");
    if (backdrop) {
      backdrop.addEventListener("click", function (ev) {
        if (ev.target === backdrop) closeModal();
      });
    }
    var closeBtn = document.getElementById("modal-close-btn");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);

    var cancelBtn = document.getElementById("modal-cancel-btn");
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
  }
});

// Hide modal: fires before HTMX swaps a 204/empty response targeting #modal-dialog
htmx.on("htmx:beforeSwap", function (e) {
  if (e.detail.target.id === "modal-dialog" && !e.detail.xhr.response) {
    closeModal();
    e.detail.shouldSwap = false;
  }
});

// Escape key closes modal
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") closeModal();
});

// ── SweetAlert2 toast system ──────────────────────────────────────────────────

document.addEventListener("messages", function (e) {
  var msgs = Array.isArray(e.detail) ? e.detail : e.detail && e.detail.value;
  if (!msgs || msgs.length === 0) return;
  var queue = Promise.resolve();
  msgs.forEach(function (msg) {
    queue = queue.then(function () {
      return Swal.fire(buildSwalConfig(msg));
    });
  });
});

function buildSwalConfig(msg) {
  var tag = (msg.tags || "info").split(" ").pop();
  var iconMap = { debug: "info", info: "info", success: "success", warning: "warning", error: "error" };
  var icon = iconMap[tag] || "info";
  var isError = icon === "error";
  return {
    text:              msg.message,
    icon:              icon,
    toast:             true,
    position:          "top-end",
    showConfirmButton: false,
    timer:             isError ? 0 : 4000,
    timerProgressBar:  !isError,
    showCloseButton:   true,
    customClass:       { popup: "swal-rms-popup" },
    didOpen: function (popup) {
      popup.addEventListener("mouseenter", Swal.stopTimer);
      popup.addEventListener("mouseleave", Swal.resumeTimer);
    },
  };
}
```

**Verify:** Search the entire JS file for `closeModal`, `showMessages`, `HX-Retarget`.
Each must appear zero times after this step (except the `closeModal` function
definition and its calls within the block above).

---

## Step 3 — Update the Base Template (`index.html`)

File: `templates/index.html` (the base layout)

Locate `<div id="modal_container">`. It must be:
- Present at the end of `<body>`, before closing `</body>`
- Empty — no children
- No classes needed — it is an invisible placeholder

```html
<div id="modal_container"></div>
```

No other change to `index.html`.

---

## Step 4 — Update the Customer Detail Template

File: `customers/customer_detail.html` (the template containing the
`customer-detail-partial` block)

Locate the outermost `<div id="customer-detail-partial">` and add the HTMX
refresh listener attributes to it:

```html
<div id="customer-detail-partial"
     hx-get="{{ request.path }}"
     hx-trigger="customerDetailChanged from:body"
     hx-swap="outerHTML">
```

This makes the partial re-fetch itself when any modal fires `customerDetailChanged`.
The `request.path` ensures it re-fetches the same URL it was rendered from,
preserving the active tab via the `?tab=` query param if present.

**Important:** `hx-boost="true"` is on `<body>`. Do NOT add `hx-push-url` here.
The re-fetch is a background data refresh, not a navigation.

---

## Step 5 — Rewrite All 8 Modal Views

File: `customer/views.py`

### 5a. Delete these helpers entirely — they must not exist:

- `_modal_success_response()`
- `_customer_detail_context()`

Search the file for both names and delete the complete function bodies.

### 5b. Standard view pattern

Every modal view must follow this exact structure. The example uses `modal_deposit`;
apply the identical structure to all 8.

```python
from django.http import HttpResponse

def modal_deposit(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related("deposit_account"), pk=pk
    )

    if request.method == "POST":
        form = TransactionForm(request.POST)
        if form.is_valid():
            try:
                customer_services.record_deposit(
                    account=customer.deposit_account,
                    amount=form.cleaned_data["amount"],
                    note=form.cleaned_data.get("note", ""),
                    user=request.user,
                    request=request,
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
        # fall through: invalid form or service exception → re-render modal
    else:
        form = TransactionForm()

    return render(request, "customers/modals/deposit_modal.html", {
        "customer": customer,
        "form": form,
    })
```

**Rules that apply to every view:**
- One view function, handles GET and POST
- `form = TheForm(request.POST)` on POST, `form = TheForm()` on GET
- Valid POST: call service → `messages.success(...)` → `HttpResponse(status=204)`
  with `HX-Trigger: customerDetailChanged`
- Service exception: `form.add_error(None, str(e))` then fall through to render
- Invalid form: fall through to render
- GET: render modal template with empty form
- No `@require_GET` decorator on any modal view
- No `HX-Retarget`, `HX-Reswap` headers anywhere
- No call to `_modal_success_response()` anywhere

### 5c. All 8 views — specific details

Apply the standard pattern above to each view, with these specifics:

**1. `modal_deposit` (pk = customer pk)**
- Form: `TransactionForm`
- Service: `customer_services.record_deposit(...)`
- Extra: after saving, handle custom date field from `request.POST.get("date")`:
  ```python
  date_str = request.POST.get("date")
  if date_str:
      try:
          txn.created_at = datetime.strptime(date_str, "%Y-%m-%d")
          txn.save(update_fields=["created_at"])
      except (ValueError, TypeError):
          pass
  ```
  Note: `record_deposit` must return the transaction object for this to work.
- Success message: `f"Deposit of ₦{form.cleaned_data['amount']:,.0f} recorded for {customer.full_name}."`
- Template: `customers/modals/deposit_modal.html`

**2. `modal_withdrawal` (pk = customer pk)**
- Form: `TransactionForm`
- Service: `customer_services.record_withdrawal(...)` (or equivalent)
- Apply same custom date handling as deposit if the service returns a txn object
- Success message: `f"Withdrawal of ₦{form.cleaned_data['amount']:,.0f} recorded for {customer.full_name}."`
- Template: `customers/modals/withdrawal_modal.html`

**3. `modal_cfa_agreement` (pk = customer pk)**
- Form: `CfaAgreementForm`
- Service: `customer_services.create_cfa_agreement(...)`
- Success message: `f"CFA agreement created for {customer.full_name}."`
- Template: `customers/modals/cfa_agreement_modal.html`
- Note: template has live XOF preview JS (`updateCfaPreview`). Do not remove or
  change any JS hooks, `data-value` attributes, or element IDs in this template.

**4. `modal_edit_cfa` (pk = CFA agreement pk, NOT customer pk)**
- Fetch: `cfa_agreement = get_object_or_404(CfaAgreement, pk=pk)`
- Also fetch customer: `customer = cfa_agreement.account.customer`
- Form: `CfaAgreementForm(request.POST or None, instance=cfa_agreement)`
  (pre-populated with existing values)
- Service: `customer_services.edit_cfa_agreement(...)` or `form.save()`
- Success message: `"CFA agreement updated."`
- Template: `customers/modals/edit_cfa_modal.html`

**5. `modal_cancel_cfa` (pk = CFA agreement pk)**
- Fetch: `cfa_agreement = get_object_or_404(CfaAgreement, pk=pk)`
- Also fetch customer: `customer = cfa_agreement.account.customer`
- Form: whatever confirmation/reason form exists for cancellation
- Service: `customer_services.cancel_agreement(cfa_agreement, user=request.user, request=request)`
- Use `messages.warning(...)` not `messages.success(...)` — this is a destructive action
- Success message: `f"CFA agreement {cfa_agreement.agreement_number} cancelled."`
- Template: `customers/modals/cancel_cfa_modal.html`

**6. `modal_cfa_disbursement` (pk = CFA agreement pk)**
- Fetch: `cfa_agreement = get_object_or_404(CfaAgreement, pk=pk)`
- Also fetch customer: `customer = cfa_agreement.account.customer`
- Form: `CfaDisbursementForm`
- Service: `customer_services.record_cfa_fulfillment(...)`
- Apply custom date handling if service returns an object with `created_at`
- Success message: `"Disbursement recorded."`
- Template: `customers/modals/cfa_disbursement_modal.html`

**7. `modal_void_cfa_disbursement` (pk = CFA fulfillment/disbursement pk)**
- Fetch: `fulfillment = get_object_or_404(CfaFulfillment, pk=pk)`
- Also fetch customer via the fulfillment's relation chain
- Form: `VoidReasonForm` (or equivalent reason field form)
- Service: `customer_services.void_cfa_fulfillment(...)`
- Success message: `"Disbursement voided."`
- Template: `customers/modals/void_cfa_disbursement_modal.html`

**8. `modal_void_transaction` (pk = transaction pk)**
- Fetch: `transaction = get_object_or_404(Transaction, pk=pk)`
- Also fetch customer via `transaction.account.customer`
- Form: `VoidReasonForm`
- Service: `customer_services.void_deposit(transaction, ...)` or equivalent void service
- Success message: `"Transaction voided."`
- Template: `customers/modals/void_transaction_modal.html`

---

## Step 6 — Rewrite All 8 Modal Templates

Every modal template must follow this exact HTML structure.
The Tailwind classes below are the standard — preserve your existing
`field-label`, `field-input`, `btn-primary`, `btn-secondary`, `summary-box`,
`card`, `card-p` utility classes exactly as they exist in the codebase.

### Standard modal template structure:

```html
{% load humanize %}
<div id="modal-backdrop"
     class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">

  <div id="modal-dialog"
       class="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6"
       hx-target="this"
       onclick="event.stopPropagation()">

    <!-- Header -->
    <div class="flex justify-between items-center mb-5">
      <h3 class="font-bold text-lg text-slate-800">MODAL TITLE HERE</h3>
      <button id="modal-close-btn"
              class="w-8 h-8 flex items-center justify-center rounded-lg
                     text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-all">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- Customer summary (include where relevant) -->
    <div class="summary-box mb-5">
      <div class="font-bold text-sm text-slate-800">{{ customer.full_name|title }}</div>
      <div class="text-xs text-slate-400 mt-1">
        Available:
        <span class="amount font-bold text-emerald-600">
          ₦{{ customer.deposit_account.cached_available_balance|floatformat:0|intcomma }}
        </span>
      </div>
    </div>

    <!-- Form -->
    <form hx-post="{% url 'MODAL_URL_NAME' object.pk %}"
          hx-target="#modal-dialog"
          hx-swap="innerHTML">
      {% csrf_token %}

      <!-- Non-field errors (service exceptions + form-level validation) -->
      {% if form.non_field_errors %}
        <div class="text-xs text-rose-600 bg-rose-50 rounded-lg px-3 py-2 mb-4">
          {% for error in form.non_field_errors %}{{ error }}{% endfor %}
        </div>
      {% endif %}

      <!-- Fields go here -->
      <div class="space-y-4">
        <!-- example field: -->
        <div>
          <label class="field-label">Amount (₦)</label>
          <input type="number" name="amount" class="field-input font-mono"
                 placeholder="0.00" step="0.01" min="1" required
                 value="{{ form.amount.value|default:'' }}">
          {% for error in form.amount.errors %}
            <p class="text-xs text-rose-600 mt-1">{{ error }}</p>
          {% endfor %}
        </div>
      </div>

      <!-- Actions -->
      <div class="flex gap-3 mt-6">
        <button type="button" id="modal-cancel-btn" class="btn-secondary flex-1">
          Cancel
        </button>
        <button type="submit" class="btn-primary flex-1">
          SUBMIT LABEL HERE
        </button>
      </div>
    </form>
  </div>
</div>
```

### Critical attributes — must be exact:

| Element | Required attribute | Value | Reason |
|---|---|---|---|
| Outer backdrop div | `id` | `modal-backdrop` | JS backdrop-click listener attaches here |
| Inner dialog div | `id` | `modal-dialog` | `htmx:beforeSwap` checks this id to detect success |
| Inner dialog div | `hx-target` | `this` | Validation error re-renders inside dialog, not whole container |
| × button | `id` | `modal-close-btn` | JS close listener attaches here |
| Cancel button | `id` | `modal-cancel-btn` | JS close listener attaches here |
| Form | `hx-target` | `#modal-dialog` | POST responses swap into dialog |
| Form | `hx-swap` | `innerHTML` | Replace dialog contents, not the dialog itself |
| Form | `hx-post` | `{% url '...' pk %}` | Must POST to same view that rendered the GET |

### Do NOT put any of these on any element in the template:
- `onclick="closeModal()"` — JS function no longer exists
- `onclick="if(event.target===this) closeModal()"` — same
- `hx-on:click="..."` inline event handlers for closing
- `hx-target="#modal_container"` on the form — wrong target
- `hx-swap="outerHTML"` on the form

### Apply this structure to all 8 modal templates:

**deposit_modal.html** — fields: amount (number), date (date, default today), note (text optional)
**withdrawal_modal.html** — fields: amount (number), date (date, default today), note (text optional)
**cfa_agreement_modal.html** — fields: whatever CfaAgreementForm renders. Preserve the
  `id="cfa-xof-preview"`, `id="cfa-naira-preview"`, `id="cfa-rate-preview"`,
  `id="cfa-available-balance"` elements and `oninput="updateCfaPreview(...)"` exactly.
**edit_cfa_modal.html** — same fields as cfa_agreement_modal but pre-populated via `instance`
**cancel_cfa_modal.html** — confirmation UI; use `btn-danger` or red `btn-primary` for submit
**cfa_disbursement_modal.html** — fields: amount (number), date (date, default today), note (text optional)
**void_cfa_disbursement_modal.html** — field: reason (text or textarea)
**void_transaction_modal.html** — field: reason (text or textarea)

---

## Step 7 — Clean Up URL Patterns

File: `customer/urls.py` (or wherever modal URLs are defined)

Delete all URL patterns whose name ends with `_submit`. Each modal must have exactly
one URL, handling both GET and POST.

```python
# CORRECT — one URL per modal
path("modal/deposit/<uuid:pk>/", modal_deposit, name="modal_deposit"),
path("modal/withdrawal/<uuid:pk>/", modal_withdrawal, name="modal_withdrawal"),
path("modal/cfa/<uuid:pk>/", modal_cfa_agreement, name="modal_cfa_agreement"),
path("modal/cfa/<uuid:pk>/edit/", modal_edit_cfa, name="modal_edit_cfa"),
path("modal/cfa/<uuid:pk>/cancel/", modal_cancel_cfa, name="modal_cancel_cfa"),
path("modal/cfa/<uuid:pk>/disbursement/", modal_cfa_disbursement, name="modal_cfa_disbursement"),
path("modal/disbursement/<uuid:pk>/void/", modal_void_cfa_disbursement, name="modal_void_cfa_disbursement"),
path("modal/transaction/<uuid:pk>/void/", modal_void_transaction, name="modal_void_transaction"),
```

The URL path strings above may differ from what already exists in the file.
Match the existing path strings. The only change is: remove `_submit` variants.

Run this after editing URLs to confirm zero `_submit` references remain:
```bash
grep -rn "_submit" customer/templates/ customer/urls.py customer/views.py
```

---

## Step 8 — Update `AGENTS.md`

File: `AGENTS.md`

Find the **Common Pitfalls** section. Locate the bullet point that starts with:
`**Modal form pattern**:`

Replace it with this:

```markdown
- **Modal form pattern**: Every modal uses a single view (GET + POST). GET renders
  the modal template into `#modal_container`. Valid POST returns `HttpResponse(status=204)`
  with `HX-Trigger: customerDetailChanged` — the JS `htmx:beforeSwap` listener
  detects the empty 204 and calls `closeModal()`. Invalid POST or service exception
  re-renders the modal template as a 200 response; `hx-target="this"` on `#modal-dialog`
  keeps the swap inside the dialog. Toast notifications come from `messages.success()`
  / `messages.warning()` / `messages.error()` — `HtmxMessageMiddleware` attaches them
  to `HX-Trigger` automatically. Never use `_modal_success_response()`,
  `_customer_detail_context()`, `HX-Retarget`, `HX-Reswap`, or split views.
  Canonical reference: `modal_deposit` in `customer/views.py` and
  `customers/modals/deposit_modal.html`.
```

---

## Step 9 — Verification

Run every check below. Each must pass before the task is complete.

### 9a. Grep checks — all must return zero results

```bash
grep -rn "_modal_success_response" .
grep -rn "_customer_detail_context" .
grep -rn "closeModal" templates/
grep -rn "modal_deposit_submit\|modal_withdrawal_submit\|modal_cfa_agreement_submit\|modal_edit_cfa_submit\|modal_cancel_cfa_submit\|modal_cfa_disbursement_submit\|modal_void_cfa_disbursement_submit\|modal_void_transaction_submit" .
grep -rn "HX-Retarget" customer/
grep -rn "HX-Reswap" customer/
grep -rn "MiddlewareMixin" middleware.py
grep -rn "showMessages" static/
grep -rn "hx-target=\"#modal_container\"" customers/templates/customers/modals/
```

### 9b. Structural checks — inspect manually

- [ ] `middleware.py` — class uses `__init__`/`__call__`, no `content_type` check,
      skips redirects with `300 <= status_code < 400`
- [ ] `main.js` — `htmx.on("htmx:afterSwap", ...)` listener present
- [ ] `main.js` — `htmx.on("htmx:beforeSwap", ...)` listener present, checks
      `e.detail.target.id === "modal-dialog"` and `!e.detail.xhr.response`
- [ ] `main.js` — `document.addEventListener("messages", ...)` reads `msg.message`
      and `msg.tags`
- [ ] Every modal template has `id="modal-backdrop"` on outer div
- [ ] Every modal template has `id="modal-dialog"` and `hx-target="this"` on inner div
- [ ] Every modal template has `id="modal-close-btn"` on × button
- [ ] Every modal template has `id="modal-cancel-btn"` on Cancel button
- [ ] Every modal form has `hx-target="#modal-dialog"` and `hx-swap="innerHTML"`
- [ ] `customer-detail-partial` div has `hx-trigger="customerDetailChanged from:body"`
- [ ] No modal view has `@require_GET`
- [ ] Every modal view returns `HttpResponse(status=204)` with
      `response["HX-Trigger"] = "customerDetailChanged"` on success

### 9c. Manual functional test — repeat for all 8 modals

1. Click the trigger button → modal opens over the page ✓
2. Click the × button → modal closes, page unchanged ✓
3. Click the backdrop (outside the white card) → modal closes ✓
4. Press Escape → modal closes ✓
5. Click Cancel → modal closes ✓
6. Submit with invalid/missing required field → modal stays open, error shown inline,
   no full page reload ✓
7. Submit a service-level error (e.g. insufficient balance) → modal stays open,
   error appears in the non-field-errors block ✓
8. Submit valid data → modal closes, SweetAlert2 toast appears top-right,
   customer detail balances/data refresh without full page reload ✓
9. Open modal, submit with error, then close → reopen modal → no stale errors
   visible ✓

### 9d. Run the test suite

```bash
python manage.py test customer
```

All tests must pass. If a test was previously asserting on `_modal_success_response`
behaviour or redirect responses from modal views, update the test to assert on
`status_code == 204` and `HX-Trigger` header presence instead.
