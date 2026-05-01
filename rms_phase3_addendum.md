# RMS Phase 3 — Addendum: JS→HTMX Conversion Rules & SweetAlert2 Toast System

> Append this to the Phase 3 protocol (v2). Read this BEFORE starting any template task.
> This addendum governs two things:
> 1. How every JavaScript interaction in the prototype maps to its HTMX equivalent
> 2. The complete replacement of the toast/message system with SweetAlert2

---

## PART 1 — JAVASCRIPT TO HTMX CONVERSION RULEBOOK

The prototype (`v4-prototype.html`) is a self-contained static demo — it uses
JavaScript to simulate everything that Django + HTMX will handle in the real app.
Every JS pattern in the prototype has a direct HTMX equivalent.

**The rule:** When you see JS doing something in the prototype, find it in the table
below and implement the HTMX version instead. Never port the JS directly.

---

### Pattern A — Page navigation (`showPage()`)

**Prototype JS:**
```javascript
function showPage(id, navEl) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const pg = document.getElementById('page-' + id);
  if (pg) pg.classList.add('active');
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  if (navEl) navEl.classList.add('active');
  if (id === 'sale_create') { wStep = 1; renderWizard(); }
  document.getElementById('content').scrollTo(0, 0);
}
```

```html
<!-- Prototype usage -->
<a class="nav-link" onclick="showPage('customers', this)">Customers</a>
<tr onclick="showPage('customer_detail', null)">...</tr>
<button onclick="showPage('sale_create', null)">New Sale</button>
```

**HTMX equivalent:**
```html
<!-- Sidebar nav link -->
<a href="{% url 'customers' %}"
   hx-get="{% url 'customers' %}"
   hx-target="#main_body"
   hx-push-url="true"
   hx-indicator="#body_spinner"
   class="nav-link {% if request.resolver_match.url_name == 'customers' %}active{% endif %}">
  Customers
</a>

<!-- Clickable table row (navigate to detail) -->
<tr class="cursor-pointer hover:bg-gray-50"
    hx-get="{% url 'customer_detail' pk=customer.pk %}"
    hx-target="#main_body"
    hx-push-url="true"
    hx-indicator="#body_spinner">
  ...
</tr>

<!-- Action button navigating to another page -->
<a href="{% url 'sale_create' %}"
   hx-get="{% url 'sale_create' %}"
   hx-target="#main_body"
   hx-push-url="true"
   class="btn-primary btn-sm">
  New Sale
</a>
```

**Key difference:** The prototype uses a fake single-page app with `display:none` pages.
The real app has actual URLs. Every `showPage()` call becomes an `hx-get` to a real URL.
The `active` class on nav links is set server-side via `request.resolver_match.url_name`,
not by JavaScript.

---

### Pattern B — Tab switching (`switchTab()`)

**Prototype JS:**
```javascript
function switchTab(btn, paneId) {
  const container = btn.closest('.page') || document.body;
  container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const panes = container.querySelectorAll('.tab-pane');
  panes.forEach(p => p.classList.remove('active'));
  const target = document.getElementById(paneId);
  if (target) target.classList.add('active');
}
```

```html
<!-- Prototype usage -->
<button class="tab-btn active" onclick="switchTab(this,'cdt-agreements')">Purchase Agreements</button>
```

**HTMX equivalent:**
```html
<!-- Tab button -->
<button hx-get="{% url 'customer_detail' pk=customer.pk %}?tab=agreements"
        hx-target="#tab_content"
        hx-push-url="true"
        hx-indicator="#body_spinner"
        class="tab-btn {% if active_tab == 'agreements' %}active{% endif %}">
  Purchase Agreements
</button>

<!-- Tab content container — server renders the correct tab -->
<div id="tab_content">
  {% if active_tab == 'agreements' %}
    {% include "customers/partials/agreements_tab.html" %}
  {% elif active_tab == 'cfa' %}
    {% include "customers/partials/cfa_tab.html" %}
  {% elif active_tab == 'transactions' %}
    {% include "customers/partials/transactions_tab.html" %}
  {% elif active_tab == 'sales' %}
    {% include "customers/partials/sales_tab.html" %}
  {% endif %}
</div>
```

The view reads `tab = request.GET.get('tab', 'agreements')` and sets the active tab
class server-side. The `active` class on the correct button is set by Django template
logic — no JS needed. The HTMX request returns only the `#tab_content` partial.

---

### Pattern C — Modal open (`openModal()`)

**Prototype JS:**
```javascript
function openModal(id) {
  const m = document.getElementById(id);
  m.classList.add('open');
  document.body.style.overflow = 'hidden';
}
```

```html
<!-- Prototype usage -->
<button onclick="openModal('modal-deposit')">+ Deposit</button>
<button onclick="openModal('modal-void-sale')">Void Sale</button>
<button onclick="openModal('modal-gr')">Record Receipt</button>
```

**HTMX equivalent:**
```html
<!-- Modal trigger — loads modal HTML from server into #modal_container -->
<button hx-get="{% url 'modal_deposit' pk=customer.pk %}"
        hx-target="#modal_container"
        hx-swap="innerHTML"
        hx-indicator="#body_spinner"
        class="btn-primary btn-sm">
  + Deposit
</button>

<button hx-get="{% url 'confirm_void_sale' pk=sale.pk %}"
        hx-target="#modal_container"
        hx-swap="innerHTML"
        class="btn-danger btn-sm">
  Void Sale
</button>
```

Each modal type is a separate view returning a modal HTML fragment (no `extends`).
The `#modal_container` div in `index.html` holds the loaded modal.

---

### Pattern D — Modal close (`closeModal()`)

**Prototype JS:**
```javascript
function closeModal(id) {
  if (id) {
    document.getElementById(id).classList.remove('open');
  } else {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('open'));
  }
  const anyOpen = document.querySelector('.modal-overlay.open');
  if (!anyOpen) document.body.style.overflow = '';
}
document.querySelectorAll('.modal-overlay').forEach(m => {
  m.addEventListener('click', e => { if (e.target === m) closeModal(m.id); });
});
```

**HTMX + minimal JS (the one place JS is still needed — and it's tiny):**

This stays as vanilla JS in `app.js` because clearing `innerHTML` is simpler and
more reliable than an HTMX swap to empty. There is no HTMX-only way to do this
that is cleaner.

```javascript
// app.js — this is the ONLY JS needed for modal close
function closeModal() {
  const container = document.getElementById('modal_container');
  if (container) container.innerHTML = '';
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});
```

In the modal template, the backdrop and close button use `onclick="closeModal()"`:
```html
<div class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
     onclick="if(event.target===this) closeModal()">
  <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6"
       onclick="event.stopPropagation()">
    <button onclick="closeModal()" class="...">✕</button>
    ...
  </div>
</div>
```

After a modal form submits successfully, close the modal automatically:
```html
<form hx-post="{% url 'add_transaction' pk=customer.pk %}"
      hx-target="#main_body"
      hx-push-url="true"
      hx-on::after-request="if(event.detail.successful) closeModal()">
```

---

### Pattern E — Wizard step navigation (`wNext()`, `wPrev()`, `renderWizard()`)

**Prototype JS:**
```javascript
let wStep = 1;
function wNext() { if (wStep < 4) { wStep++; renderWizard(); } }
function wPrev() { if (wStep > 1) { wStep--; renderWizard(); } }
function renderWizard() {
  for (let i = 1; i <= 4; i++) {
    const s = document.getElementById('wstep-' + i);
    if (s) s.classList.toggle('active', i === wStep);
    const si = document.getElementById('si' + i);
    if (si) {
      si.className = 'step-ind ' + (i < wStep ? 'done' : i === wStep ? 'current' : 'future');
      si.innerHTML = i < wStep ? '<svg ...>✓</svg>' : i;
    }
    const sl = document.getElementById('sl' + i);
    if (sl) sl.className = 'text-sm ' + (i <= wStep ? 'font-bold text-slate-900' : 'text-slate-400');
  }
  const wb = document.getElementById('wizard-back');
  if (wb) wb.style.display = (wStep > 1 && wStep < 4) ? 'block' : 'none';
}
```

**HTMX equivalent — server-driven steps:**

Each wizard step is a separate URL. State passes forward as hidden inputs.
No client-side step management.

```html
<!-- Step 1 template — selecting customer -->
<!-- URL: /sales/new/ -->
<form hx-post="{% url 'sale_step2' %}"
      hx-target="#main_body"
      hx-push-url="true">
  {% csrf_token %}
  {% include "partials/wizard_steps.html" with current_step=1 %}

  <div class="card card-p">
    <h2 class="font-medium mb-4">Select Customer</h2>
    {% for customer in customers %}
    <label class="...">
      <input type="radio" name="customer_id" value="{{ customer.pk }}" required>
      <div class="flex justify-between">
        <div class="font-medium">{{ customer.full_name }}</div>
        <div class="amount text-emerald-600">
          ₦{{ customer.depositaccount.cached_available_balance|intcomma }}
        </div>
      </div>
    </label>
    {% endfor %}
  </div>

  <button type="submit" class="btn-primary w-full mt-4">
    Continue → Payment Type
  </button>
</form>

<!-- Step 2 template — payment type -->
<!-- URL: /sales/new/step2/ — receives customer_id from step 1 -->
<form hx-post="{% url 'sale_step3' %}"
      hx-target="#main_body"
      hx-push-url="true">
  {% csrf_token %}
  <input type="hidden" name="customer_id" value="{{ customer.pk }}">
  {% include "partials/wizard_steps.html" with current_step=2 %}

  <div class="card card-p">
    <div class="bg-amber-50 rounded-lg p-3 mb-5 ...">
      <!-- Selected customer summary -->
      {{ customer.full_name }} · Available:
      <span class="amount text-emerald-600">
        ₦{{ customer.depositaccount.cached_available_balance|intcomma }}
      </span>
    </div>
    <h2 class="font-medium mb-4">How is this sale being paid?</h2>

    <label class="...">
      <input type="radio" name="payment_method" value="from deposit" required>
      <div>
        <div class="font-medium">From Customer Deposit</div>
        <div class="text-sm text-gray-500 mt-1">
          Draw from deposit account. Must link to an active purchase agreement.
        </div>
        <div class="text-xs text-emerald-600 font-medium mt-1">
          Available: ₦{{ customer.depositaccount.cached_available_balance|intcomma }}
        </div>
      </div>
    </label>

    <label class="...">
      <input type="radio" name="payment_method" value="bank transfer">
      <div class="font-medium">Bank Transfer</div>
    </label>

    <label class="...">
      <input type="radio" name="payment_method" value="cash">
      <div class="font-medium">Cash</div>
    </label>
  </div>

  <div class="flex gap-3 mt-4">
    <a hx-get="{% url 'sale_create' %}"
       hx-target="#main_body"
       hx-push-url="true"
       class="btn-secondary flex-1 text-center">← Back</a>
    <button type="submit" class="btn-primary flex-1">Continue → Add Items</button>
  </div>
</form>
```

The wizard step indicator partial is rendered server-side with `current_step` in context.
No JS manages which step is active — the URL determines the step.

---

### Pattern F — Dynamic list/search filtering

**Prototype JS:**
The prototype uses static data — no filtering logic exists in JS.
Filtering in the prototype is visual-only (no actual JS filter).

**HTMX equivalent:**
```html
<div class="flex gap-3 mb-5">
  <!-- Search -->
  <div class="relative flex-1 max-w-xs">
    <input type="search"
           name="q"
           value="{{ request.GET.q }}"
           placeholder="Search..."
           hx-get="{% url 'customers' %}"
           hx-target="#list_container"
           hx-push-url="true"
           hx-trigger="keyup changed delay:300ms, search"
           hx-indicator="#body_spinner"
           class="field-input pl-9">
  </div>

  <!-- Filter dropdown -->
  <select name="filter"
          hx-get="{% url 'customers' %}"
          hx-target="#list_container"
          hx-push-url="true"
          hx-trigger="change"
          hx-include="[name='q']"
          class="field-select w-auto">
    <option value="" {% if not request.GET.filter %}selected{% endif %}>All customers</option>
    <option value="active_agreements" {% if request.GET.filter == 'active_agreements' %}selected{% endif %}>
      With active agreements
    </option>
    <option value="idle_balance" {% if request.GET.filter == 'idle_balance' %}selected{% endif %}>
      Available balance &gt; ₦1M
    </option>
  </select>

  <!-- Sort -->
  <select name="sort"
          hx-get="{% url 'customers' %}"
          hx-target="#list_container"
          hx-push-url="true"
          hx-trigger="change"
          hx-include="[name='q'],[name='filter']"
          class="field-select w-auto">
    <option value="name">Sort: Name A–Z</option>
    <option value="-available">Sort: Balance High–Low</option>
    <option value="-created">Sort: Newest first</option>
  </select>
</div>

<!-- This is the HTMX target — only this refreshes on search/filter -->
<div id="list_container">
  {% partialdef list_content inline=True %}
  <div class="card overflow-hidden">
    <table class="data-table">
      ...
    </table>
  </div>
  {% endpartialdef %}
</div>
```

The view reads `q`, `filter`, and `sort` from `request.GET` and applies them.
For HTMX requests, render only the `#list_content` partial.

---

### Pattern G — Formset add/remove row

**Prototype JS:**
```javascript
function addSaleItem() {
  const c = document.getElementById('sale-items-container');
  if (!c) return;
  const d = document.createElement('div');
  d.className = 'border border-dashed border-slate-200 rounded-xl p-5';
  d.innerHTML = `<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">...</div>`;
  c.appendChild(d);
}
// Remove: this.closest('div.border').remove()
```

**HTMX equivalent:**
See the Canonical Formset Pattern in the Phase 3 protocol (v2).
The add/remove buttons are `hx-post` requests that return the entire formset container.
No JS creates or removes DOM elements. The server re-renders the full formset section.

---

### Pattern H — CFA live preview

**Prototype JS:**
```javascript
function updateCfaPreview(amt, rate) {
  const a = parseFloat(amt) || 0;
  const r = parseFloat(rate) || 1800;
  const xof = Math.round((a / r) * 1000 / 100) * 100;
  const preview = document.getElementById('cfa-preview');
  if (preview) {
    const rows = preview.querySelectorAll('.flex.justify-between span:last-child');
    if (rows[0]) rows[0].textContent = '₦' + a.toLocaleString();
    if (rows[1]) rows[1].textContent = '₦' + r.toLocaleString() + ' / 1,000 XOF';
    if (rows[2]) rows[2].textContent = xof.toLocaleString() + ' XOF';
  }
}
```

```html
<!-- Prototype usage -->
<input type="number" ... oninput="updateCfaPreview(this.value,document.getElementById('cfaRate').value)">
<input type="number" id="cfaRate" ... oninput="updateCfaPreview(document.getElementById('cfaAmt').value,this.value)">
```

**Approach:** This stays as vanilla JS in `app.js`. It is pure client-side math with
no server data needed. It is the right tool for this job. Do not use HTMX for this.

```javascript
// app.js
function updateCfaPreview(amountInput, rateInput) {
  const amt  = parseFloat(amountInput.value) || 0;
  const rate = parseFloat(rateInput.value)   || 0;
  const xof  = rate > 0
    ? Math.round((amt / rate) * 1000 / 100) * 100
    : 0;

  const xofEl   = document.getElementById('cfa-xof-preview');
  const nairaEl = document.getElementById('cfa-naira-preview');
  const rateEl  = document.getElementById('cfa-rate-preview');

  if (xofEl)   xofEl.textContent   = xof.toLocaleString() + ' XOF';
  if (nairaEl) nairaEl.textContent = '₦' + amt.toLocaleString();
  if (rateEl)  rateEl.textContent  = '₦' + rate.toLocaleString() + ' / 1,000 XOF';

  // Balance warning
  const available = parseFloat(
    document.getElementById('cfa-available-balance')?.dataset.value || '0'
  );
  const warn = document.getElementById('cfa-balance-warn');
  if (warn) warn.classList.toggle('hidden', amt <= available);
}
```

Template inputs:
```html
<input id="id_amount_allocated"
       type="number"
       name="amount_allocated"
       class="field-input font-mono"
       oninput="updateCfaPreview(this, document.getElementById('id_exchange_rate'))">

<input id="id_exchange_rate"
       type="number"
       name="exchange_rate"
       class="field-input font-mono"
       oninput="updateCfaPreview(document.getElementById('id_amount_allocated'), this)">

<!-- Hidden element carrying the available balance from Django context -->
<span id="cfa-available-balance"
      data-value="{{ customer.depositaccount.cached_available_balance }}"
      class="hidden"></span>

<!-- Live preview panel -->
<div class="bg-amber-50 border border-amber-100 rounded-xl p-4 mt-4">
  <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
    Agreement Preview
  </div>
  <div class="space-y-2 text-sm">
    <div class="flex justify-between">
      <span class="text-gray-500">Naira locked:</span>
      <span id="cfa-naira-preview" class="amount font-medium">₦0</span>
    </div>
    <div class="flex justify-between">
      <span class="text-gray-500">Exchange rate:</span>
      <span id="cfa-rate-preview" class="amount font-medium">—</span>
    </div>
    <div class="flex justify-between border-t border-amber-100 pt-2 mt-2">
      <span class="text-gray-700 font-medium">Expected CFA:</span>
      <span id="cfa-xof-preview" class="amount font-semibold text-lg">0 XOF</span>
    </div>
  </div>
  <div id="cfa-balance-warn"
       class="hidden mt-3 text-xs text-rose-600 font-medium">
    ⚠ Amount exceeds available balance
  </div>
</div>
```

---

### Pattern I — Toast notification (`showToast()`)

**Prototype JS:**
```javascript
let toastTimer;
function showToast(msg) {
  const t = document.getElementById('toast');
  document.getElementById('toast-msg').textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 4000);
}
```

**HTMX equivalent:** See Part 2 of this document — the complete SweetAlert2 system.
`showToast()` is replaced entirely. It is never ported. It does not exist in `app.js`.

---

### Pattern J — Scan field auto-advance

**Prototype:** No JS for this — scan fields are just plain inputs in the prototype.

**Real app implementation** (small JS, appropriate here):
```javascript
// app.js
// Auto-advance from engine number field to chassis number field
// when the value reaches a minimum length (barcode scanner input)
document.addEventListener('input', function(e) {
  if (e.target.classList.contains('scan-field-engine')) {
    if (e.target.value.length >= 8) {
      const row = e.target.closest('.formset-row');
      if (row) {
        const chassisField = row.querySelector('.scan-field-chassis');
        if (chassisField) chassisField.focus();
      }
    }
  }
});
```

Scan fields use specific classes so the JS can target them:
```html
<input class="scan-field scan-field-engine" type="text"
       name="items-{{ forloop.counter0 }}-engine_number"
       placeholder="Scan or type ENG-XXXXX">
<input class="scan-field scan-field-chassis" type="text"
       name="items-{{ forloop.counter0 }}-chassis_number"
       placeholder="Scan or type CHN-XXXXX">
```

This uses event delegation on `document` so it works on HTMX-appended rows too.

---

### Complete JS-to-HTMX conversion reference table

| Prototype JS | Real implementation | JS needed? |
|---|---|---|
| `showPage(id)` — navigate to page | `hx-get` + `hx-target="#main_body"` + `hx-push-url="true"` | No |
| `showPage()` on `<tr>` click | `hx-get` on `<tr>` directly | No |
| `switchTab(btn, paneId)` | `hx-get` with `?tab=x` + server-side active class | No |
| `openModal(id)` | `hx-get` → `hx-target="#modal_container"` | No |
| `closeModal(id)` | `closeModal()` in `app.js` — sets `innerHTML=''` | Yes — 3 lines |
| Backdrop click to close modal | `onclick="if(event.target===this) closeModal()"` on backdrop | Yes — inline |
| Escape key to close modal | `keydown` listener in `app.js` | Yes — 3 lines |
| `wNext()` / `wPrev()` — wizard steps | Server-driven step URLs + hidden input state | No |
| `renderWizard()` — update step indicators | Server renders step indicator partial with `current_step` | No |
| `addSaleItem()` / `addSaleRow()` | `hx-post` with `name="add_row"` + server re-render | No |
| Remove row (formset) | `hx-post` with `name="remove_row"` value=index | No |
| `updateCfaPreview()` | `updateCfaPreview()` in `app.js` — pure math | Yes — stays JS |
| `showToast()` | SweetAlert2 via `HX-Trigger` header (Part 2) | Yes — 10 lines |
| Search/filter lists | `hx-get` with `hx-trigger="keyup delay:300ms"` | No |
| Date range filter | `hx-get` with `hx-trigger="change"` on `<select>` | No |
| Scan field auto-advance | Event delegation in `app.js` | Yes — 10 lines |
| Active nav link highlight | `request.resolver_match.url_name` in template | No |
| Login/logout | Standard Django auth URLs | No |

**Summary:** Of all the JS in the prototype, only 6 things survive in `app.js`:
1. `closeModal()` — 3 lines
2. `Escape` key listener — 3 lines
3. Backdrop click — inline `onclick` attribute (not in `app.js`)
4. `updateCfaPreview()` — 20 lines
5. Scan field auto-advance — 10 lines
6. SweetAlert2 message listener — 15 lines (Part 2)

Total `app.js`: under 60 lines. That is the complete JavaScript footprint of the rebuilt app.

---

## PART 2 — SWEETALERT2 TOAST SYSTEM

### What is being replaced and why

**Current system problems:**
- `HtmxMessageMiddleware` appends toast HTML to every HTMX response by string concatenation
- Toast HTML uses Alpine.js (`x-show`, `x-init`, `@click`) for show/hide — Alpine is gone
- The OOB swap mechanism adds a hidden `<div id="message-container">` to responses
- This couples the toast rendering to every view response
- If a view returns a redirect (using `HX-Redirect`), the toast HTML never reaches the browser
- Toast auto-dismiss uses `setTimeout` inside Alpine init — fragile

**New system:**
Django messages → middleware reads them → serialises to JSON in `HX-Trigger` response
header → HTMX fires a browser event → one `addEventListener` in `app.js` calls SweetAlert2.

No HTML appended to responses. No OOB swaps. No Alpine. Works on partial swaps,
full page loads, and HTMX redirects. Messages consumed once, never double-displayed.

---

### Step 1 — Install SweetAlert2

Add to `requirements.txt` — no, SweetAlert2 is a frontend library.
Download the minified JS and CSS and place in static:

```bash
# Download from https://cdn.jsdelivr.net/npm/sweetalert2@11/dist/
static/js/sweetalert2.min.js
static/css/sweetalert2.min.css
```

Or load from CDN in `index.html` (acceptable for a desktop-local app):
```html
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/sweetalert2@11/dist/sweetalert2.min.css">
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11/dist/sweetalert2.all.min.js"></script>
```

---

### Step 2 — Rewrite `middleware.py`

Replace the entire current `HtmxMessageMiddleware` with this:

```python
# middleware.py
import json
from django.contrib.messages import get_messages
from django.contrib.messages.storage.base import LEVEL_TAGS
from django.utils.deprecation import MiddlewareMixin


class HtmxMessageMiddleware(MiddlewareMixin):
    """
    For HTMX requests: intercepts pending Django messages and serialises them
    into the HX-Trigger response header as a 'showMessages' event payload.

    The client's app.js listens for the 'showMessages' event and calls SweetAlert2.

    For non-HTMX requests: messages render normally in the base template.

    This replaces the old system that appended OOB toast HTML to response bodies.
    """

    # Map Django message level tags to SweetAlert2 icon names
    ICON_MAP = {
        'debug':   'info',
        'info':    'info',
        'success': 'success',
        'warning': 'warning',
        'error':   'error',
    }

    def process_response(self, request, response):
        # Only intercept HTMX requests
        if not request.headers.get('HX-Request'):
            return response

        # Only intercept HTML responses (not JSON, not redirects)
        content_type = response.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response

        # Read and consume all pending messages
        storage = get_messages(request)
        message_list = list(storage)

        if not message_list:
            return response

        # Serialise messages
        messages_data = []
        for message in message_list:
            tag = message.tags.split()[-1] if message.tags else 'info'
            messages_data.append({
                'text':  str(message),
                'icon':  self.ICON_MAP.get(tag, 'info'),
                'level': tag,
            })

        # Read any existing HX-Trigger header — must merge, not overwrite
        existing_trigger = response.get('HX-Trigger', None)

        if existing_trigger:
            try:
                trigger_data = json.loads(existing_trigger)
            except (json.JSONDecodeError, ValueError):
                # Existing header is a plain event name string, not JSON
                trigger_data = {existing_trigger: True}
        else:
            trigger_data = {}

        # Add our showMessages event to the trigger payload
        trigger_data['showMessages'] = messages_data

        response['HX-Trigger'] = json.dumps(trigger_data)

        return response
```

**How HX-Trigger works:** HTMX reads the `HX-Trigger` response header after every
request and fires the named event(s) on the `document`. The value can be a simple
event name (`"myEvent"`) or a JSON object mapping event names to data payloads
(`{"myEvent": {"key": "value"}}`). The event fires after the HTMX swap completes.

---

### Step 3 — Full page load rendering (non-HTMX requests)

For full page loads (initial navigation, login redirect etc.), messages aren't
intercepted by the middleware. They must still render in the base template.

Add this block to `index.html`, just before `</body>`:

```html
{# Render Django messages on full page load via SweetAlert2 #}
{% if messages %}
<script>
document.addEventListener('DOMContentLoaded', function() {
  const messages = [
    {% for message in messages %}
    {
      text:  "{{ message|escapejs }}",
      icon:  "{{ message.tags|escapejs }}",
      level: "{{ message.level_tag|escapejs }}"
    }{% if not forloop.last %},{% endif %}
    {% endfor %}
  ];
  if (typeof Swal !== 'undefined') {
    showMessages(messages);
  }
});
</script>
{% endif %}
```

This handles login success, permission errors, and any view that does a full redirect.

---

### Step 4 — The client-side listener and SweetAlert2 config in `app.js`

Add this to `app.js`:

```javascript
// ── SweetAlert2 message system ────────────────────────────────────────────────

// Listen for HTMX-triggered showMessages event (fired from HX-Trigger header)
document.addEventListener('showMessages', function(e) {
  const messages = e.detail && e.detail.value ? e.detail.value : e.detail;
  if (Array.isArray(messages) && messages.length > 0) {
    showMessages(messages);
  }
});

// Shared function — called by both HTMX event and full page script block
function showMessages(messages) {
  if (!messages || messages.length === 0) return;

  // Queue messages — show one at a time if multiple
  let queue = Promise.resolve();
  messages.forEach(function(msg) {
    queue = queue.then(function() {
      return Swal.fire(buildSwalConfig(msg));
    });
  });
}

function buildSwalConfig(msg) {
  const isError = msg.icon === 'error' || msg.level === 'error';

  return {
    text:              msg.text,
    icon:              msg.icon || 'info',
    toast:             true,          // toast mode — small, corner notification
    position:          'top-end',     // top-right corner
    showConfirmButton: false,
    timer:             isError ? 0 : 4000,    // errors stay until dismissed
    timerProgressBar:  !isError,
    showCloseButton:   true,
    customClass: {
      popup:      'swal-rms-popup',
      title:      'swal-rms-title',
      closeButton:'swal-rms-close',
    },
    didOpen: function(popup) {
      // Pause timer on hover
      popup.addEventListener('mouseenter', Swal.stopTimer);
      popup.addEventListener('mouseleave', Swal.resumeTimer);
    },
  };
}
```

**How `HX-Trigger` event detail works with HTMX:**

When HTMX sees `HX-Trigger: {"showMessages": [...]}`, it fires a custom DOM event:
```javascript
// HTMX fires this internally:
document.dispatchEvent(new CustomEvent('showMessages', {
  detail: { value: [...messages array...] }
}));
```

So `e.detail.value` is the array. The `e.detail && e.detail.value ? e.detail.value : e.detail`
line handles both the HTMX format (`{value: [...]}`) and the direct call format `([...])`.

---

### Step 5 — SweetAlert2 custom styling (match design system)

Add to `static/css/custom.css` (a small CSS file included after Tailwind):

```css
/* Match SweetAlert2 toasts to RMS design system */

.swal-rms-popup {
  font-family: 'DM Sans', sans-serif !important;
  font-size: 14px !important;
  border-radius: 12px !important;
  box-shadow: 0 10px 40px rgba(0,0,0,0.12) !important;
  padding: 12px 16px !important;
  min-width: 280px !important;
  max-width: 380px !important;
}

.swal2-toast.swal-rms-popup {
  background: #111827 !important;  /* sidebar dark — matches design */
  color: #f9fafb !important;
}

/* Icon colours */
.swal2-toast .swal2-icon.swal2-success {
  color: #10b981 !important;
  border-color: #10b981 !important;
}
.swal2-toast .swal2-icon.swal2-error {
  color: #f43f5e !important;
  border-color: #f43f5e !important;
}
.swal2-toast .swal2-icon.swal2-warning {
  color: #f59e0b !important;
  border-color: #f59e0b !important;
}
.swal2-toast .swal2-icon.swal2-info {
  color: #3b82f6 !important;
  border-color: #3b82f6 !important;
}

/* Timer progress bar */
.swal2-toast .swal2-timer-progress-bar {
  background: #d97706 !important;  /* accent amber */
}

/* Close button */
.swal2-toast .swal2-close {
  color: #6b7280 !important;
}
.swal2-toast .swal2-close:hover {
  color: #f9fafb !important;
}
```

Add to `index.html` after tailwind.css:
```html
<link rel="stylesheet" href="{% static 'css/custom.css' %}">
```

---

### Step 6 — Update `index.html` to load SweetAlert2 and remove old toast HTML

**Remove from `index.html`:**
```html
<!-- DELETE this — the old Alpine-powered toast -->
{% include "partials/toast.html" %}
```

**Add to `index.html` before `</body>`:**
```html
<!-- SweetAlert2 -->
<script src="{% static 'js/sweetalert2.min.js' %}"></script>
<!-- Or CDN: -->
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11/dist/sweetalert2.all.min.js"></script>

<!-- app.js (includes showMessages listener) -->
<script src="{% static 'js/app.js' %}"></script>

<!-- Full page load messages -->
{% if messages %}
<script>
document.addEventListener('DOMContentLoaded', function() {
  showMessages([
    {% for message in messages %}
    { text: "{{ message|escapejs }}", icon: "{{ message.tags }}" }{% if not forloop.last %},{% endif %}
    {% endfor %}
  ]);
});
</script>
{% endif %}
```

---

### Step 7 — Update every view to use `messages` properly

Views should use the correct message level — it maps to the SweetAlert2 icon:

```python
from django.contrib import messages

# Success actions
messages.success(request, 'Purchase order PO-2024-A1B2 created.')
messages.success(request, f'Sale {sale.sale_number} voided. Inventory restored.')
messages.success(request, f'Deposit of ₦{amount:,.0f} recorded for {customer.full_name}.')

# Errors (validation failures, business rule violations)
messages.error(request, 'Cannot void: stock has already been sold or assembled.')
messages.error(request, 'Agreement value exceeds available balance.')
messages.error(request, 'Please correct the errors below.')

# Warnings (non-blocking alerts)
messages.warning(request, f'Stock for {product.modelname} is below threshold.')

# Info (neutral status updates)
messages.info(request, 'No changes were made.')
```

**Message text guidelines:**
- Always include the object identifier (sale number, customer name, amount)
- Write in plain English — the business owner reads these
- For errors: say what went wrong and why, not just "Error occurred"
- For success: say what happened, not just "Success"

**Message formatting rule:** Money amounts in messages should be formatted in Python:
```python
messages.success(
    request,
    f'Deposit of ₦{amount:,.0f} recorded for {customer.full_name}. '
    f'New available balance: ₦{account.cached_available_balance:,.0f}'
)
```

---

### Step 8 — Delete `templates/partials/toast.html` and `templates/partials/toasts_oob.html`

After Task 25 (base templates) is complete and SweetAlert2 is wired:
```bash
rm templates/partials/toast.html
rm templates/partials/toasts_oob.html  # if it exists
rm templates/partials/delete_toast.html  # if it exists
```

These files must not exist after Phase 3. Any template that `{% include %}`s them
will throw a `TemplateDoesNotExist` error — which is the correct signal that the
old reference was not cleaned up.

---

### How the complete flow works end-to-end

**HTMX partial swap (most common case):**

1. User clicks "Void Sale" → modal opens
2. User fills void reason, clicks "Confirm Void"
3. `hx-post` sends request to `void_sale_view`
4. View calls `services.void_sale()`, then `messages.success(request, 'Sale voided...')`
5. View returns HTMX redirect: `HttpResponseClientRedirect(reverse('sale_detail', pk=pk))`
6. `HtmxMessageMiddleware.process_response()` runs on the redirect response:
   - Reads the pending success message
   - Serialises it to JSON
   - Sets `HX-Trigger: {"showMessages": [{"text": "Sale voided...", "icon": "success"}]}`
7. HTMX receives the redirect, navigates to sale detail page
8. HTMX fires the `showMessages` event on `document`
9. `app.js` listener calls `showMessages([{text: ..., icon: 'success'}])`
10. SweetAlert2 shows a dark toast in the top-right corner
11. Toast auto-dismisses after 4 seconds

**Full page load (login, initial load):**

1. Django renders `index.html`
2. `{% if messages %}` block renders a `<script>` tag with the messages as JSON
3. On `DOMContentLoaded`, `showMessages()` is called directly
4. SweetAlert2 fires

**Form validation error (partial swap returning the form):**

1. User submits a form with invalid data
2. View adds `messages.error(request, 'Please correct the errors below.')`
3. View re-renders the form with validation errors displayed inline
4. `HtmxMessageMiddleware` intercepts the partial HTML response
5. Sets `HX-Trigger: {"showMessages": [{"text": "...", "icon": "error"}]}`
6. HTMX swaps the form, then fires `showMessages`
7. SweetAlert2 shows error toast (no auto-dismiss — user must click close)
8. Form shows inline field errors below each field (Django form errors, not toast)

**Note on error messages:** Toasts are for action confirmation and system-level errors.
Inline field validation errors (`{{ form.field.errors }}`) are rendered inside the form,
below the relevant field — they do not use SweetAlert2. Toasts are for the broader outcome.

---

### Updated middleware registration

Update `mrms/settings.py`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',  # must be before ours
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'middleware.HtmxMessageMiddleware',   # must be last
]
```

`MessageMiddleware` must come before `HtmxMessageMiddleware` because our middleware
reads from the message storage that `MessageMiddleware` sets up.

---

### Delete the old `partials/toasts_oob.html` template

The old middleware called `render_to_string("partials/toasts_oob.html", ...)`.
This template is no longer used — the new middleware sets a header, not HTML.
Delete it. If the file is missing, the old middleware would throw an error —
which is the correct signal to verify the new middleware is active.

---

## FINAL `app.js` — COMPLETE FILE

This is the complete `static/js/app.js`. Every line is accounted for. Nothing else
needs to be written.

```javascript
// static/js/app.js
// RMS Retail Management System — client-side JS
// Philosophy: server does the work. JS fills the gaps HTMX cannot.
// Total: ~60 lines. No frameworks. No build step required.

'use strict';

// ── Modal management ──────────────────────────────────────────────────────────

function closeModal() {
  const container = document.getElementById('modal_container');
  if (container) container.innerHTML = '';
}

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeModal();
});

// ── SweetAlert2 toast system ──────────────────────────────────────────────────

// HTMX fires this event when HX-Trigger header contains 'showMessages'
document.addEventListener('showMessages', function(e) {
  const messages = (e.detail && e.detail.value) ? e.detail.value : e.detail;
  if (Array.isArray(messages)) showMessages(messages);
});

// Called directly on full page load (from inline script in index.html)
function showMessages(messages) {
  if (!messages || messages.length === 0) return;
  let queue = Promise.resolve();
  messages.forEach(function(msg) {
    queue = queue.then(function() {
      return Swal.fire(buildSwalConfig(msg));
    });
  });
}

function buildSwalConfig(msg) {
  const isError = msg.icon === 'error';
  return {
    text:              msg.text,
    icon:              msg.icon || 'info',
    toast:             true,
    position:          'top-end',
    showConfirmButton: false,
    timer:             isError ? 0 : 4000,
    timerProgressBar:  !isError,
    showCloseButton:   true,
    customClass: { popup: 'swal-rms-popup' },
    didOpen: function(popup) {
      popup.addEventListener('mouseenter', Swal.stopTimer);
      popup.addEventListener('mouseleave', Swal.resumeTimer);
    },
  };
}

// ── CFA Agreement live preview ────────────────────────────────────────────────

function updateCfaPreview(amountInput, rateInput) {
  const amt  = parseFloat(amountInput.value) || 0;
  const rate = parseFloat(rateInput.value)   || 0;
  const xof  = rate > 0 ? Math.round((amt / rate) * 1000 / 100) * 100 : 0;

  const set = function(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  set('cfa-xof-preview',   xof.toLocaleString() + ' XOF');
  set('cfa-naira-preview',  '₦' + amt.toLocaleString());
  set('cfa-rate-preview',   '₦' + rate.toLocaleString() + ' / 1,000 XOF');

  const available = parseFloat(
    document.getElementById('cfa-available-balance')?.dataset.value || '0'
  );
  const warn = document.getElementById('cfa-balance-warn');
  if (warn) warn.classList.toggle('hidden', amt <= available || amt === 0);
}

// ── Barcode scanner: auto-advance engine → chassis field ─────────────────────

document.addEventListener('input', function(e) {
  if (e.target.classList.contains('scan-field-engine') && e.target.value.length >= 8) {
    const row = e.target.closest('.formset-row');
    if (row) {
      const next = row.querySelector('.scan-field-chassis');
      if (next) next.focus();
    }
  }
});
```

---

## VERIFICATION CHECKLIST FOR TOAST SYSTEM

After Task 25 is complete, verify the toast system works before proceeding to Task 27:

- [ ] Create a test view that calls `messages.success(request, 'Test success message')`
      and returns an HTMX partial response — confirm SweetAlert2 toast appears
- [ ] Call `messages.error(request, 'Test error message')` — confirm toast has no
      auto-dismiss timer and requires manual close
- [ ] Do a full page load on any page with a pending message — confirm toast appears
      via the inline `<script>` block
- [ ] Confirm `HX-Trigger` header is set correctly using browser DevTools Network tab
- [ ] Confirm no `hx-swap-oob` toast HTML appears anywhere in responses
- [ ] Confirm `templates/partials/toast.html` has been deleted and no template
      tries to `{% include %}` it
- [ ] Confirm `HtmxMessageMiddleware` is the last middleware in `MIDDLEWARE` list
