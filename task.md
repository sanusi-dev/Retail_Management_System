# TASK: Refactor Purchase Agreement Line Item Formset to HTMX Server-State Pattern

## Overview

Refactor the `PurchaseAgreement` create/edit form so that all formset row
manipulation (add row, remove row) is handled by the server via HTMX, not by
JavaScript. JavaScript is retained **only** for the available-balance
calculation. Django owns all formset state.

---

## Constraints — Read Before Touching Anything

- App name: `customers`
- Formset prefix: `"item"` — never change this.
- The inline formset factory has already been set up correctly:
  `PurchaseAgreementLineItemFormSet = inlineformset_factory(PurchaseAgreement, PurchaseAgreementLineItem, ...)`.
  Do **not** revert it to `modelformset_factory`.
- The base formset class is `BasePurchaseAgreementLineItemFormSet(BaseInlineFormSet)`.
- The `manage_purchase_agreements` view handles both create (`pk=None`) and
  edit (`pk=<uuid>`). Do not split it.
- Template engine: Django templates with `django-template-partials`.
- CSS framework: Tailwind CSS utility classes only — no custom CSS files.
- HTMX is already loaded globally. Do not add script tags for it.
- Do **not** use `hx-trigger="load"` anywhere in this task.
- All HTMX requests from the add/remove buttons must use `hx-post` and
  `hx-include="closest form"` so the full current form state is sent.
- The HTMX swap target for both add and remove is `#formset-container`
  with `hx-swap="outerHTML"`.
- `manage_purchase_agreement_line_item` view and its URL
  `add_purchase_agreement_line_item` are being **deleted** as part of this task.

---

## Step 1 — Delete the Old View and URL

### File: `customers/views.py`

Delete the entire `manage_purchase_agreement_line_item` function.

### File: `customers/urls.py`

Remove this entry:

```python
path(
    "add_purchase_agreement_line_item",
    manage_purchase_agreement_line_item,
    name="add_purchase_agreement_line_item",
),
```

---

## Step 2 — Add Two New URLs

### File: `customers/urls.py`

Add these two entries. Place them directly after the
`edit_purchase_agreement` entry:

```python
path(
    "purchase_agreement/line_item/add",
    agreement_line_item_add,
    name="agreement_line_item_add",
),
path(
    "purchase_agreement/line_item/remove/<int:index>",
    agreement_line_item_remove,
    name="agreement_line_item_remove",
),
```

---

## Step 3 — Add Two New Views

### File: `customers/views.py`

Add both functions below. Insert them immediately after the
`manage_purchase_agreements` function.

### 3a — `agreement_line_item_add`

```python
def agreement_line_item_add(request):
    """
    Receives the full current form state via POST (hx-include="closest form").
    Appends one empty row by incrementing TOTAL_FORMS and seeding blank fields.
    Returns the re-rendered #formset-container partial.
    """
    post_data = request.POST.copy()
    total_forms = int(post_data.get("item-TOTAL_FORMS", 0))

    post_data[f"item-{total_forms}-product"] = ""
    post_data[f"item-{total_forms}-quantity_ordered"] = ""
    post_data[f"item-{total_forms}-price_per_unit"] = ""
    post_data["item-TOTAL_FORMS"] = total_forms + 1

    formset = PurchaseAgreementLineItemFormSet(post_data, prefix="item")

    return render(
        request,
        "customers/partials/purchase_agreement_formset.html",
        {"formset": formset},
    )
```

### 3b — `agreement_line_item_remove`

```python
def agreement_line_item_remove(request, index):
    """
    Receives the full current form state via POST (hx-include="closest form")
    and the index of the row to operate on from the URL.

    Logic:
    - If the row has a pk (item-{index}-id is non-empty): the row is an
      existing DB record. Toggle its DELETE flag. If it was unmarked, mark it
      "on". If it was already "on", unmark it (undo).
    - If the row has no pk: it is a new unsaved row. Shift all rows above
      this index down by one, decrement TOTAL_FORMS, drop the row entirely.

    Returns the re-rendered #formset-container partial.
    """
    post_data = request.POST.copy()
    total_forms = int(post_data.get("item-TOTAL_FORMS", 0))
    pk_value = post_data.get(f"item-{index}-id", "").strip()

    if pk_value:
        # Existing DB record — toggle DELETE
        already_deleted = post_data.get(f"item-{index}-DELETE", "") == "on"
        if already_deleted:
            post_data.pop(f"item-{index}-DELETE", None)
        else:
            post_data[f"item-{index}-DELETE"] = "on"

        formset = PurchaseAgreementLineItemFormSet(post_data, prefix="item")

    else:
        # New unsaved row — remove by shifting indexes
        import urllib.parse
        from django.http import QueryDict

        line_fields = ["id", "product", "quantity_ordered", "price_per_unit", "DELETE"]
        new_data = {}
        new_index = 0

        for i in range(total_forms):
            if i == index:
                continue
            for field in line_fields:
                old_key = f"item-{i}-{field}"
                if old_key in post_data:
                    new_data[f"item-{new_index}-{field}"] = post_data[old_key]
            new_index += 1

        new_data["item-TOTAL_FORMS"] = new_index
        new_data["item-INITIAL_FORMS"] = post_data.get("item-INITIAL_FORMS", 0)
        new_data["item-MIN_NUM_FORMS"] = post_data.get("item-MIN_NUM_FORMS", 0)
        new_data["item-MAX_NUM_FORMS"] = post_data.get("item-MAX_NUM_FORMS", 1000)

        encoded = urllib.parse.urlencode(new_data, doseq=True)
        rebuilt = QueryDict(encoded, mutable=True)

        formset = PurchaseAgreementLineItemFormSet(rebuilt, prefix="item")

    return render(
        request,
        "customers/partials/purchase_agreement_formset.html",
        {"formset": formset},
    )
```

---

## Step 4 — Create the Formset Container Partial

### File: `customers/templates/customers/partials/purchase_agreement_formset.html`

**Create this file.** It is the HTMX swap target (`id="formset-container"`).
Both `agreement_line_item_add` and `agreement_line_item_remove` render this
partial and return it as `outerHTML`.

```html
{% load humanize %}
<div id="formset-container">
  {{ formset.management_form }}
  <div class="space-y-4" id="items-container">
    {% for form in formset %}
      {% include 'customers/partials/purchase_agreement_line_item_form.html' with form=form %}
    {% endfor %}
  </div>

  <button type="button"
          hx-post="{% url 'agreement_line_item_add' %}"
          hx-include="closest form"
          hx-target="#formset-container"
          hx-swap="outerHTML"
          class="mt-4 text-sm text-brand-600 hover:text-brand-700 font-bold flex items-center gap-1.5 transition-colors">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
    </svg>
    Add Line Item
  </button>
</div>
```

---

## Step 5 — Rewrite the Line Item Row Partial

### File: `customers/templates/customers/partials/purchase_agreement_line_item_form.html`

**Replace the entire file** with the content below. Key behaviours:

- `form.hidden_fields` renders the hidden `id` field that identifies existing
  DB records. Never remove this loop.
- When `form.DELETE.value` is truthy, the row renders with a strikethrough
  style and a ↩ undo button instead of the ✕ remove button. The undo button
  hits the same `agreement_line_item_remove` URL, which toggles DELETE off.
- Do **not** use the `disabled` attribute on inputs — disabled inputs are not
  submitted by the browser, which would break the form state on re-submit.
  Use `tabindex="-1"` and `pointer-events-none` (Tailwind) instead.
- The `{{ form.DELETE }}` checkbox is always rendered inside a `hidden` div so
  its value is submitted on the final form POST. Do not remove it.
- `forloop.counter0` is used as the index in the remove URL — this is correct
  because it matches Django's 0-based formset row numbering.

```html
{% load humanize %}
{% if form.DELETE.value %}
  {# Row is marked for deletion — show strikethrough, undo button #}
  <div class="item-form-row border border-rose-300 bg-rose-50 rounded-xl p-5 opacity-60">
    {% for hidden in form.hidden_fields %}{{ hidden }}{% endfor %}
    <div class="grid grid-cols-1 sm:grid-cols-12 gap-4 line-through pointer-events-none select-none">
      <div class="sm:col-span-5">
        <label class="field-label text-rose-400">Product</label>
        <select name="{{ form.product.html_name }}" class="field-select" tabindex="-1">
          {% for product in form.product.field.queryset %}
            <option value="{{ product.pk }}"
                    {% if form.product.value|stringformat:"s" == product.pk|stringformat:"s" %}selected{% endif %}>
              {{ product.brand.name|title }} {{ product.modelname|title }}
            </option>
          {% endfor %}
        </select>
      </div>
      <div class="sm:col-span-3">
        <label class="field-label text-rose-400">Quantity</label>
        <input type="number"
               name="{{ form.quantity_ordered.html_name }}"
               class="field-input font-mono"
               tabindex="-1"
               value="{{ form.quantity_ordered.value|default:'' }}">
      </div>
      <div class="sm:col-span-3">
        <label class="field-label text-rose-400">Price per Unit (₦)</label>
        <input type="number"
               name="{{ form.price_per_unit.html_name }}"
               class="field-input font-mono"
               tabindex="-1"
               value="{{ form.price_per_unit.value|default:'' }}">
      </div>
      <div class="sm:col-span-1 flex items-end justify-center pointer-events-auto">
        <button type="button"
                hx-post="{% url 'agreement_line_item_remove' forloop.counter0 %}"
                hx-include="closest form"
                hx-target="#formset-container"
                hx-swap="outerHTML"
                class="w-8 h-8 flex items-center justify-center rounded-lg
                       text-rose-400 hover:text-slate-600 hover:bg-slate-100 transition-all"
                title="Undo removal">
          ↩
        </button>
      </div>
    </div>
    <div class="hidden">{{ form.DELETE }}</div>
    {% if form.instance.pk %}
      <div class="mt-3 pt-3 border-t border-rose-200">
        <div class="flex items-center gap-2 text-xs text-rose-400">
          <span class="font-mono">{{ form.instance.line_number }}</span>
          <span>·</span>
          <span>Will be deleted on save</span>
        </div>
      </div>
    {% endif %}
  </div>

{% else %}
  {# Normal row #}
  <div class="item-form-row border border-slate-200 rounded-xl p-5
              {% if form.errors %}border-rose-300 bg-rose-50{% endif %}">
    {% for hidden in form.hidden_fields %}{{ hidden }}{% endfor %}
    <div class="grid grid-cols-1 sm:grid-cols-12 gap-4">
      <div class="sm:col-span-5">
        <label class="field-label">Product</label>
        <select name="{{ form.product.html_name }}" class="field-select" required>
          <option value="">Select a product</option>
          {% for product in form.product.field.queryset %}
            <option value="{{ product.pk }}"
                    {% if form.product.value|stringformat:"s" == product.pk|stringformat:"s" %}selected{% endif %}>
              {{ product.brand.name|title }} {{ product.modelname|title }} — Stock: {{ product.inventory.quantity|default:0 }}
            </option>
          {% endfor %}
        </select>
        {% if form.product.errors %}
          {% for error in form.product.errors %}
            <p class="text-xs text-rose-600 mt-1">{{ error }}</p>
          {% endfor %}
        {% endif %}
      </div>

      <div class="sm:col-span-3">
        <label class="field-label">Quantity</label>
        <input type="number"
               name="{{ form.quantity_ordered.html_name }}"
               class="field-input font-mono"
               placeholder="1" min="1" required
               value="{{ form.quantity_ordered.value|default:'' }}">
        {% if form.quantity_ordered.errors %}
          {% for error in form.quantity_ordered.errors %}
            <p class="text-xs text-rose-600 mt-1">{{ error }}</p>
          {% endfor %}
        {% endif %}
      </div>

      <div class="sm:col-span-3">
        <label class="field-label">Price per Unit (₦)</label>
        <input type="number"
               name="{{ form.price_per_unit.html_name }}"
               class="field-input font-mono"
               placeholder="0.00" step="0.01" min="0" required
               value="{{ form.price_per_unit.value|default:'' }}">
        {% if form.price_per_unit.errors %}
          {% for error in form.price_per_unit.errors %}
            <p class="text-xs text-rose-600 mt-1">{{ error }}</p>
          {% endfor %}
        {% endif %}
      </div>

      <div class="sm:col-span-1 flex items-end justify-center">
        <button type="button"
                hx-post="{% url 'agreement_line_item_remove' forloop.counter0 %}"
                hx-include="closest form"
                hx-target="#formset-container"
                hx-swap="outerHTML"
                class="remove-form-row w-8 h-8 flex items-center justify-center rounded-lg
                       text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-all"
                title="Remove line item">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="hidden">{{ form.DELETE }}</div>

    {% if form.instance.pk %}
      <div class="mt-3 pt-3 border-t border-slate-100">
        <div class="flex items-center gap-2 text-xs text-slate-400">
          <span class="font-mono">{{ form.instance.line_number }}</span>
          <span>·</span>
          <span>Line total:
            <span class="amount font-bold text-slate-600">
              ₦{{ form.instance.total_line|floatformat:0|intcomma }}
            </span>
          </span>
          {% if form.instance.quantity_fulfilled_accross_all_versions > 0 %}
            <span>·</span>
            <span class="text-emerald-600 font-medium">
              {{ form.instance.quantity_fulfilled_accross_all_versions }} fulfilled
            </span>
          {% endif %}
        </div>
      </div>
    {% endif %}
  </div>
{% endif %}
```

---

## Step 6 — Update the Main Template

### File: `customers/templates/customers/purchase_agreement_form.html`

#### 6a — Replace the formset block inside the Line Items card

Find this block inside the `<!-- Line Items Card -->` section:

```html
{{ formset.management_form }}
<div class="space-y-4" id="items-container">
  {% for form in formset %}
    {% include 'customers/partials/purchase_agreement_line_item_form.html' with form=form %}
  {% endfor %}
</div>
<!-- Add line item button -->
<button type="button"
        id="add-item-btn"
        hx-get="{% url 'add_purchase_agreement_line_item' %}"
        hx-target="#items-container"
        hx-swap="beforeend"
        hx-push-url="false"
        class="mt-4 text-sm text-brand-600 hover:text-brand-700 font-bold flex items-center gap-1.5 transition-colors">
  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
  </svg>
  Add Line Item
</button>
```

Replace it with a single include:

```html
{% include 'customers/partials/purchase_agreement_formset.html' %}
```

#### 6b — Replace the entire `<script>` block

Remove the existing script block completely and replace with this one.
It handles **only** the available balance calculation. No row management,
no field renaming, no click handlers:

```html
<script>
  function updateAgreementTotal() {
    let total = 0;
    document.querySelectorAll('.item-form-row').forEach(function (row) {
      // Skip rows marked for deletion
      const deleteInput = row.querySelector('input[name$="-DELETE"]');
      if (deleteInput && deleteInput.checked) return;

      const qty = parseFloat(
        row.querySelector('input[name$="-quantity_ordered"]')?.value
      ) || 0;
      const price = parseFloat(
        row.querySelector('input[name$="-price_per_unit"]')?.value
      ) || 0;
      total += qty * price;
    });

    const totalEl = document.getElementById('agreement-total');
    if (totalEl) {
      totalEl.textContent = '₦' + total.toLocaleString('en-NG', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      });
    }

    const balanceAfterEl = document.getElementById('balance-after');
    const availableEl = document.getElementById('balance-after-row');
    if (balanceAfterEl && availableEl) {
      const available = parseFloat(availableEl.dataset.available || '0');
      const remaining = available - total;
      balanceAfterEl.textContent = '₦' + remaining.toLocaleString('en-NG', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      });
      balanceAfterEl.classList.toggle('text-rose-600', remaining < 0);
      balanceAfterEl.classList.toggle('text-slate-800', remaining >= 0);
    }
  }

  // Recalculate when user types in quantity or price fields
  document.addEventListener('input', function (e) {
    if (
      e.target.name?.endsWith('-quantity_ordered') ||
      e.target.name?.endsWith('-price_per_unit')
    ) {
      updateAgreementTotal();
    }
  });

  // Recalculate after HTMX swaps in the formset container (add/remove row)
  document.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail.target?.id === 'formset-container') {
      updateAgreementTotal();
    }
  });

  document.addEventListener('DOMContentLoaded', updateAgreementTotal);
</script>
```

---

## Step 7 — Verification Checklist

The agent must verify each item manually before declaring the task complete.

### URLs
- [ ] `add_purchase_agreement_line_item` URL no longer exists in `urls.py`
- [ ] `agreement_line_item_add` URL exists and maps to `agreement_line_item_add` view
- [ ] `agreement_line_item_remove/<int:index>` URL exists and maps to `agreement_line_item_remove` view

### Views
- [ ] `manage_purchase_agreement_line_item` function no longer exists in `views.py`
- [ ] `agreement_line_item_add` function exists in `views.py`
- [ ] `agreement_line_item_remove` function exists in `views.py`
- [ ] Both new views return the `purchase_agreement_formset.html` partial

### Templates
- [ ] `purchase_agreement_formset.html` exists at `customers/templates/customers/partials/`
- [ ] `purchase_agreement_formset.html` root element has `id="formset-container"`
- [ ] `purchase_agreement_formset.html` renders `{{ formset.management_form }}`
- [ ] `purchase_agreement_line_item_form.html` renders `{% for hidden in form.hidden_fields %}{{ hidden }}{% endfor %}` in both branches
- [ ] `purchase_agreement_line_item_form.html` renders `{{ form.DELETE }}` inside a hidden div in both branches
- [ ] `purchase_agreement_line_item_form.html` remove/undo buttons use `hx-post`, `hx-include="closest form"`, `hx-target="#formset-container"`, `hx-swap="outerHTML"`
- [ ] Main template `purchase_agreement_form.html` uses `{% include 'customers/partials/purchase_agreement_formset.html' %}` inside the Line Items card
- [ ] Main template script block contains **no** click handlers, no `updateLineNumbers`, no `htmx:afterSwap` row-management logic — only `updateAgreementTotal`
- [ ] No `hx-get` anywhere in the formset-related templates (all formset mutations are `hx-post`)

### Behaviour
- [ ] Opening create form shows 1 empty row (controlled by `extra=1` on the factory)
- [ ] Clicking "Add Line Item" appends a new empty row without page reload
- [ ] Clicking ✕ on a new (unsaved) row removes it completely, indexes are contiguous
- [ ] Clicking ✕ on an existing (saved) row marks it with strikethrough, shows ↩ button
- [ ] Clicking ↩ on a marked row restores it to normal
- [ ] Submitting the form with a marked row deletes the DB record
- [ ] Available balance calculation updates when quantity or price inputs change
- [ ] Available balance calculation updates after add/remove swaps

---

## Files Changed Summary

| Action | File |
|---|---|
| Modified | `customers/urls.py` |
| Modified | `customers/views.py` |
| Modified | `customers/templates/customers/purchase_agreement_form.html` |
| Modified | `customers/templates/customers/partials/purchase_agreement_line_item_form.html` |
| Created  | `customers/templates/customers/partials/purchase_agreement_formset.html` |