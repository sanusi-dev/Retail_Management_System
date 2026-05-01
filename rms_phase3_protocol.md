
---

## WHAT PHASE 3 IS — AND WHAT IT IS NOT

Phase 3 **builds** the new UI directly from the prototype. It does not convert, migrate,
or incrementally update the existing templates. The existing templates are reference
material only — consulted for context variable names and URL names, never preserved
for structure.

**The mental model for every task:**
1. Open `v4-prototype.html` and find the page being built
2. Open the current view file to understand what context is available and what URLs exist
3. Write a new template from scratch using the prototype as the visual spec
4. Wire it to the view using HTMX and `django-template-partials`
5. Delete the old template file when the new one works

**What happens to existing templates:**
They are deleted at the end of each task — not archived, not kept alongside the new file.
Two templates for the same page create confusion. The prototype is the spec; the old
template is no longer the truth once the new one works.

**What does NOT change in Phase 3:**
- URL names (do not rename any existing URLs, unless necessary, maybe the new ui need a different routing flow)
- View function names - only if necessary
- Context variable names (the view already provides these — use them (ony if necessary in order to not cause confusion))
- Model field names
- The service layer built in Phase 2

---

## CRITICAL FACTS FROM CODEBASE AUDIT

The agent must know these before starting any task.

**Alpine.js is in the current bundle — it is not coming forward.**
The current `bundle.js` includes Alpine.js with `@alpinejs/persist`. It handles sidebar
collapse state, active nav highlighting, and some customer detail layout logic.
None of this comes forward. The prototype has no Alpine. All interactivity is HTMX
or the minimal vanilla JS written in Task 26 (`app.js`).

**`bundle.js` dies with `django-tailwind` (Task 7).**
After Task 7, there is no Node pipeline and no bundle. The replacement is
`static/js/app.js` (written in Task 26) loaded directly via `<script>` tag.

**`formset.js` is not carried forward.**
All dynamic formset behaviour is replaced by the pure HTMX server-state pattern
(see the Canonical Formset Pattern section). The file is deleted in Task 26.


**Template locations stay in their app directories — do not centralise.**
```
customer/templates/customers/       ← customer templates
inventory/templates/inventory/      ← inventory templates
supply_chain/templates/supply_chain/ ← supply chain templates
templates/                          ← base, shared partials only
```

---

## PARTIALS PHILOSOPHY — WHEN TO SPLIT AND WHEN NOT TO

`django-template-partials` is powerful because it can extract **any section** of a
template as a reusable partial — without splitting the file into separate files.
This means you can keep a template whole and still reuse parts of it.

**The rule: keep templates whole unless there is a concrete reason to split.**

### When to use a partial

1. **HTMX swap targets** — when an HTMX request returns only a section of a page
   (tab content, list body, formset container), that section must be a partial.
   ```html
   {% partialdef tab_content inline=True %}
     {# this section can be returned alone for HTMX requests #}
   {% endpartialdef %}
   ```

2. **Identical content in 2+ templates** — if the exact same HTML block appears in
   multiple templates, extract it into a partial and `{% include %}` it.

3. **Modals** — modal HTML fragments are always separate files (they don't extend
   `index.html` and are returned as standalone HTML by HTMX).

### When NOT to use a partial

1. **Don't create a partial for every component.** A card, a table row, a badge —
   these are just HTML in the template. Don't extract them unless they're reused.

2. **Don't split a page into partials "for cleanliness."** A 300-line template is
   fine. A template with 15 partials of 20 lines each is harder to follow.

3. **Don't create partials proactively.** If you're not sure whether something will
   be reused, leave it inline. Extract it later when the second use case appears.

**The goal:** Fewer, more complete templates. Not a soup of tiny partial files.

---

## JAVASCRIPT PHILOSOPHY — MINIMAL, PURPOSEFUL, SERVER-FIRST

The JS footprint of this app is intentionally tiny. The server owns state. HTMX
handles interactivity. JS fills the gaps that HTMX cannot.

### What JS should do

- **Close modals** — clearing `innerHTML` is simpler in JS than any HTMX approach
- **Escape key listener** — 3 lines, no HTMX equivalent
- **CFA live preview** — pure client-side math, no server roundtrip needed
- **Scan field auto-advance** — focus management on barcode scanner input
- **SweetAlert2 listener** — receives messages from `HX-Trigger` header

### What JS should NOT do

- **Don't manipulate formset state** — no counting rows, no renaming fields, no
  reindexing `name` attributes. This is what `formset.js` did and it was brittle.
  The server-state pattern replaces all of it.
- **Don't manage wizard steps** — the server owns step state via URLs and hidden
  inputs. No `wNext()`/`wPrev()` in the real app.
- **Don't do client-side routing** — every navigation is an `hx-get` to a real URL.
- **Don't initialise UI libraries** — no Select2, no Alpine, no Chart.js. Native
  selects, HTMX, and inline SVGs handle everything.
- **Don't write JS "just in case"** — if HTMX can do it, HTMX does it.

### The test

Before writing any JS, ask:
1. Can HTMX do this? → Use HTMX
2. Is this pure math with no server data? → JS is fine
3. Is this 3-10 lines of simple DOM manipulation? → JS is fine
4. Does this require tracking state across interactions? → Server should own that state
5. Am I reimplementing something a browser native feature does? → Use the native feature

**If the answer to #4 is yes, the JS approach is almost always wrong.** Server state
is the pattern. Client-side state management is the path to `formset.js` territory.

### The app.js budget

The entire `static/js/app.js` should be under 60 lines. If it's growing beyond that,
something that should be server-driven has crept into client-side JS. Stop and
redesign the interaction to use HTMX server responses instead.

---

## CANONICAL FORMSET PATTERN (Pure HTMX — Server-State)

This pattern replaces `formset.js` entirely. Every dynamic formset in the system uses
this exact approach. Study it once and apply it consistently.

### The core idea

The server owns all formset state. When the user adds or removes a row, the entire
current form state is sent to the server, the server adjusts the formset
(adding/removing a form), and re-renders just the formset section. No JS counts
rows, no JS renames fields, no JS manages DELETE checkboxes. Django's formset
machinery handles all of it on the server.

### Step-by-step: Purchase Order form as the canonical example

**1. The formset partial template**

```html
{# supply_chain/po/partials/_formset.html — does NOT extend index.html #}
{% load widget_tweaks %}

<div id="formset-container">
  {{ item_formset.management_form }}

  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-slate-100">
        <th class="text-left py-3 px-4 text-xs text-slate-500 font-medium uppercase">Product</th>
        <th class="text-right py-3 px-4 text-xs text-slate-500 font-medium uppercase">Qty</th>
        <th class="text-right py-3 px-4 text-xs text-slate-500 font-medium uppercase">Unit Price (₦)</th>
        <th class="py-3 px-4"></th>
      </tr>
    </thead>
    <tbody>
      {% for form in item_formset %}
      {% if not form.initial or not form.instance.pk %}
        {# New (unsaved) row — visible, removable #}
        <tr class="border-b border-slate-50 item-form-row">
          {% for hidden in form.hidden_fields %}{{ hidden }}{% endfor %}
          <td class="py-3 px-4">
            {% render_field form.product class="field-select" %}
          </td>
          <td class="py-3 px-4">
            {% render_field form.ordered_quantity class="field-input text-right font-mono" min="1" %}
          </td>
          <td class="py-3 px-4">
            {% render_field form.unit_price_at_order class="field-input text-right font-mono" min="0" %}
          </td>
          <td class="py-3 px-4 text-right">
            <button type="button"
                    name="remove_row"
                    value="{{ forloop.counter0 }}"
                    hx-post="{{ form_action_url }}"
                    hx-target="#formset-container"
                    hx-swap="outerHTML"
                    hx-include="closest form"
                    class="text-rose-400 hover:text-rose-600 transition-colors">
              <svg class="w-4 h-4" ...>✕</svg>
            </button>
          </td>
        </tr>
      {% else %}
        {# Existing (saved) row — show DELETE toggle #}
        <tr class="border-b border-slate-50 item-form-row
                   {% if form.DELETE.value %}opacity-40 line-through{% endif %}">
          {% for hidden in form.hidden_fields %}{{ hidden }}{% endfor %}
          <td class="py-3 px-4">
            {% render_field form.product class="field-select" %}
          </td>
          <td class="py-3 px-4">
            {% render_field form.ordered_quantity class="field-input text-right font-mono" %}
          </td>
          <td class="py-3 px-4">
            {% render_field form.unit_price_at_order class="field-input text-right font-mono" %}
          </td>
          <td class="py-3 px-4 text-right">
            {% if form.DELETE.value %}
              {# Already marked for delete — show undo button #}
              {{ form.DELETE }}
              <button type="button"
                      name="restore_row"
                      value="{{ forloop.counter0 }}"
                      hx-post="{{ form_action_url }}"
                      hx-target="#formset-container"
                      hx-swap="outerHTML"
                      hx-include="closest form"
                      class="text-xs text-brand-600 hover:text-brand-800 font-medium">
                Undo
              </button>
            {% else %}
              {{ form.DELETE }}
              <button type="button"
                      name="remove_row"
                      value="{{ forloop.counter0 }}"
                      hx-post="{{ form_action_url }}"
                      hx-target="#formset-container"
                      hx-swap="outerHTML"
                      hx-include="closest form"
                      class="text-rose-400 hover:text-rose-600 transition-colors">
                <svg class="w-4 h-4" ...>✕</svg>
              </button>
            {% endif %}
          </td>
        </tr>
      {% endif %}
      {% endfor %}
    </tbody>
  </table>

  {# Add row button #}
  <div class="mt-3">
    <button type="button"
            name="add_row"
            value="1"
            hx-post="{{ form_action_url }}"
            hx-target="#formset-container"
            hx-swap="outerHTML"
            hx-include="closest form"
            class="text-sm text-brand-600 hover:text-brand-700 font-medium
                   flex items-center gap-1">
      <svg class="w-4 h-4" ...>+</svg>
      Add item
    </button>
  </div>

</div>
```

**2. The view — handles add, remove, and final submission in one function - Maybe some helper function for readablility so the function wont be too long**

```python
def manage_purchases(request, pk=None):
    instance = get_object_or_404(PurchaseOrder, pk=pk) if pk else None
    queryset = instance.po_items.all() if instance else PurchaseOrderItem.objects.none()

    # Determine what triggered the request
    is_adding  = 'add_row'    in request.POST
    is_removing = 'remove_row' in request.POST
    is_restoring = 'restore_row' in request.POST
    is_htmx_formset = is_adding or is_removing or is_restoring

    if request.method == 'POST' and not is_htmx_formset:
        # ── Real form submission ──────────────────────────────────────────────
        form    = PurchaseOrderForm(request.POST, instance=instance)
        formset = PurchaseOrderItemFormSet(request.POST, queryset=queryset, prefix='items')
        if form.is_valid() and formset.is_valid():
            services.process_po(form, formset, request.user)
            messages.success(request, 'Purchase order saved.')
            return redirect('purchases')
        # Fall through to re-render with errors

    elif is_htmx_formset:
        # ── HTMX formset manipulation ─────────────────────────────────────────
        data = request.POST.copy()
        total_forms = int(data.get('items-TOTAL_FORMS', 1))

        if is_adding:
            # Increment TOTAL_FORMS — Django will render an extra empty form
            data['items-TOTAL_FORMS'] = total_forms + 1

        elif is_removing:
            remove_index = int(request.POST.get('remove_row'))
            # Check if this row has a database id (existing record)
            row_id = data.get(f'items-{remove_index}-id', '')
            if row_id:
                # Existing row — mark for DELETE via Django's mechanism
                data[f'items-{remove_index}-DELETE'] = 'on'
            else:
                # New row — remove it by shifting subsequent rows down
                # and decrementing TOTAL_FORMS
                new_data = {}
                new_index = 0
                for i in range(total_forms):
                    if i == remove_index:
                        continue  # skip the removed row
                    for key in list(data.keys()):
                        if key.startswith(f'items-{i}-'):
                            suffix = key[len(f'items-{i}-'):]
                            new_data[f'items-{new_index}-{suffix}'] = data[key]
                    new_index += 1
                # Preserve management form and non-item fields
                for key, value in data.items():
                    if not key.startswith('items-') or key in (
                        'items-INITIAL_FORMS', 'items-MIN_NUM_FORMS', 'items-MAX_NUM_FORMS'
                    ):
                        new_data[key] = value
                new_data['items-TOTAL_FORMS'] = new_index
                data = new_data

        elif is_restoring:
            restore_index = int(request.POST.get('restore_row'))
            data[f'items-{restore_index}-DELETE'] = ''

        form    = PurchaseOrderForm(request.POST, instance=instance)
        formset = PurchaseOrderItemFormSet(data, queryset=queryset, prefix='items')

        # Return only the formset container — no full page render
        context = {
            'po_form': form,
            'item_formset': formset,
            'form_action_url': reverse('edit_po', kwargs={'pk': pk}) if pk else reverse('add_po'),
        }
        return render(request, 'supply_chain/po/partials/_formset.html', context)

    else:
        # ── GET request — initial render ──────────────────────────────────────
        form    = PurchaseOrderForm(instance=instance)
        formset = PurchaseOrderItemFormSet(queryset=queryset, prefix='items')

    form_action_url = (
        reverse('edit_po', kwargs={'pk': instance.pk}) if instance
        else reverse('add_po')
    )
    context = {
        'po_form': form,
        'item_formset': formset,
        'form_action_url': form_action_url,
    }

    if request.htmx:
        return HttpResponse(
            render_to_string('supply_chain/po/form.html#content', context, request=request)
        )
    return render(request, 'supply_chain/po/form.html', context)
```

**3. The main form template — includes the formset partial**

```html
{# supply_chain/po/form.html #}
{% extends 'index.html' %}
{% load static humanize widget_tweaks %}
{% load template_partials %}

{% block content %}
{% partialdef content inline=True %}
<div class="p-8 max-w-3xl">

  {# Page header #}
  <div class="flex items-center gap-3 mb-6">
    <button onclick="history.back()" class="text-slate-400 hover:text-slate-700">
      <svg ...>←</svg>
    </button>
    <h1 class="text-xl font-semibold">
      {% if instance %}Edit {{ instance.po_number }}{% else %}New Purchase Order{% endif %}
    </h1>
  </div>

  <form id="po-form"
        method="post"
        action="{{ form_action_url }}">
    {% csrf_token %}

    {# PO header fields #}
    <div class="card card-p mb-5">
      <h2 class="font-medium mb-4">Order Details</h2>
      <div class="grid grid-cols-2 gap-4">
        <div class="col-span-2">
          <label class="field-label">Supplier</label>
          {% render_field po_form.supplier class="field-select" %}
          {% if po_form.supplier.errors %}
          <p class="text-xs text-rose-500 mt-1">{{ po_form.supplier.errors|join:", " }}</p>
          {% endif %}
        </div>
        <div>
          <label class="field-label">Order Date</label>
          {% render_field po_form.order_date class="field-input" type="date" %}
        </div>
      </div>
    </div>

    {# Line items — the formset partial lives here #}
    <div class="card overflow-hidden mb-5">
      <div class="flex items-center justify-between px-5 pt-4 pb-3 border-b border-slate-50">
        <div class="font-medium text-sm">Order Lines</div>
      </div>
      <div class="p-5">
        {% include "supply_chain/po/partials/_formset.html" %}
      </div>
    </div>

    {# Non-field errors from formset #}
    {% if item_formset.non_form_errors %}
    <div class="bg-rose-50 border border-rose-200 rounded-lg p-3 mb-4 text-sm text-rose-700">
      {% for error in item_formset.non_form_errors %}
      <p>{{ error }}</p>
      {% endfor %}
    </div>
    {% endif %}

    {# Submit #}
    <div class="flex gap-3">
      <a href="{% url 'purchases' %}"
         hx-get="{% url 'purchases' %}"
         hx-target="#main_body"
         hx-push-url="true"
         class="btn-secondary flex-1 text-center">Cancel</a>
      <button type="submit" class="btn-primary flex-1">
        {% if instance %}Save Changes{% else %}Create Purchase Order{% endif %}
      </button>
    </div>
  </form>

</div>
{% endpartialdef %}
{% endblock content %}
```

### Apply this pattern to these forms

Every form with dynamic rows follows the exact same view pattern and partial structure:

| Form | View function | Formset | Partial template |
|---|---|---|---|
| Purchase Order | `manage_purchases()` | `PurchaseOrderItemFormSet` | `po/partials/_formset.html` |
| Transformation/Assembly | `manage_transformations()` | `TransformationItemFormset` | `inventory/partials/_formset.html` |
| Goods Receipt | `manage_goods_receipt()` | `GoodsReceiptItemFormset` | `goods_receipts/partials/_formset.html` |
| Purchase Agreement | `manage_agreement()` | `PurchaseAgreementLineItemFormSet` | `customers/partials/_agreement_formset.html` |
| Sale (Boxed items) | `record_sale()` step 3 | `BoxedSaleFormSet` | `sales/partials/_boxed_formset.html` |
| Sale (Coupled items) | `record_sale()` step 3 | `CoupledSaleFormSet` | `sales/partials/_coupled_formset.html` |

The sale form manages two formsets simultaneously (boxed and coupled items). The view
handles `add_row_boxed`, `remove_row_boxed`, `add_row_coupled`, `remove_row_coupled`
as separate POST keys. Each formset partial has its own `id` for HTMX targeting.

### What `formset.js` did vs what this replaces it with

| Old behaviour (formset.js) | New behaviour (pure HTMX) |
|---|---|
| JS counts `.item-form-row` elements to get next index | Server reads `TOTAL_FORMS` from POST data |
| JS intercepts `htmx:configRequest` to inject `index` param | Server detects `add_row` in POST directly |
| Server creates empty form with manually set prefix | Server increments `TOTAL_FORMS` and Django handles the rest |
| JS regex-renames all field `name` and `id` attrs on remove | Server removes the row and re-renders — no renaming |
| Two removal paths: DOM remove (new rows) vs DELETE checkbox (saved rows) | One path: server detects if row has `id`, handles accordingly |
| `htmx:afterSwap` updates `TOTAL_FORMS` after HTMX swap | Not needed — server already returns correct `TOTAL_FORMS` |
| Select2 not re-initialised on new rows | No Select2 — native selects work without re-init |

---

## TEMPLATE MAP

Every template in the codebase mapped to its task. Consult for reference variables.

### Base & Global (Task 25)

| File | Action | Notes |
|---|---|---|
| `templates/index.html` | **Rewrite** | Remove Alpine, remove `{% tailwind_css %}`, add DM fonts, add `#modal_container`, fixed sidebar layout |
| `templates/partials/sidebar.html` | **Rewrite** | Remove Alpine state, fixed 240px, grouped nav sections, active state via `request.resolver_match.url_name` |
| `templates/partials/spinner.html` | Keep | Already correct — htmx-indicator |
| `templates/partials/toast.html` | **Update** | Match prototype dark toast style (keep OOB mechanism) |
| `templates/partials/pagination.html` | **Update** | Update CSS to match design system |
| `templates/partials/non_field_error.html` | **Update** | Rose-coloured alert box |
| `templates/partials/form_buttons.html` | **Update** | Use `btn-primary` / `btn-secondary` classes |
| `templates/partials/badge.html` | **Create** | New — renders badge from `status` variable |
| `templates/partials/modal_container.html` | **Create** | `<div id="modal_container"></div>` — HTMX modal mount |
| `templates/partials/header.html` | **Delete** | Headers are now per-page |
| `templates/partials/overlay.html` | **Delete** | No overlay system in new design |
| `templates/partials/mega_menu.html` | **Delete** | Replaced by sidebar |
| `templates/partials/htmx_preloader.html` | **Delete** | Merged into spinner.html |
| `templates/partials/plus_icon.html` | **Delete** | Inline SVGs only |
| `templates/partials/delete_toast.html` | **Delete** | Merged into toast.html |
| `templates/partials/table_filter.html` | **Delete** | Filter pattern is per-page now |
| `templates/partials/search_results_*.html` | **Delete** | Rebuilt inline in each list template |

### Dashboard (Task 27)

| File | Action |
|---|---|
| `templates/dashboard.html` | **Rewrite** — action alerts panel, KPIs, revenue SVG chart, top products, recent tables, date range filter |

### Customer Module (Tasks 28–30)

| File | Action |
|---|---|
| `customer/templates/customers/customers.html` | **Rewrite** — balance columns in table, filter/search |
| `customer/templates/customers/customer_detail.html` | **Rewrite** — financial summary panel, 4 HTMX tabs |
| `customer/templates/customers/customer_form.html` | **Rewrite** — modal fragment (no extend) |
| `customer/templates/customers/customer_transaction_form.html` | **Rewrite** — deposit/withdrawal modal fragment |
| `customer/templates/customers/customer_transactions.html` | **Rewrite** — transactions tab partial |
| `customer/templates/customers/partials/customer_wallet.html` | **Rewrite** — financial summary panel partial |
| `customer/templates/customers/partials/purchase_agreements_list.html` | **Rewrite** — progress bar layout |
| `customer/templates/customers/partials/cfa_agreements_list.html` | **Rewrite** — CFA progress layout |
| `customer/templates/customers/partials/cfa_list.html` | **Rewrite** — disbursement list |
| `customer/templates/customers/partials/transaction_row.html` | **Rewrite** — transaction table row |
| `customer/templates/customers/purchase_agreement_form.html` | **Rewrite** — modal + server-state formset |
| `customer/templates/customers/partials/purchase_agreement_line_item_form.html` | **Rewrite** — formset partial |
| `customer/templates/customers/cfa_agreement_form.html` | **Rewrite** — modal + live XOF preview (vanilla JS) |
| `customer/templates/customers/cfa_fulfillment_form.html` | **Rewrite** — modal fragment |
| `templates/customers/partials/agreement_options.html` | Keep/update — HTMX-loaded dropdown |
| `templates/customers/partials/agreement_line_item_options.html` | Keep/update — HTMX-loaded dropdown |
| `customer/templates/customers/sales/` (all) | Handled in Task 31–32 |

### Sales Module (Tasks 31–32)

| File | Action |
|---|---|
| `customer/templates/customers/sales/sales.html` | **Rewrite** — list with filters |
| `customer/templates/customers/sales/sale_detail.html` | **Rewrite** — sale info, void trigger |
| `customer/templates/customers/sales/record_sale.html` | **Rewrite** — 4-step HTMX wizard |
| `customer/templates/customers/sales/modals/void_sale_confirm.html` | **Create** — modal fragment |

### Inventory Module (Task 33)

| File | Action |
|---|---|
| `inventory/templates/inventory/product/product_list.html` | **Rewrite** |
| `inventory/templates/inventory/product/product_detail.html` | **Rewrite** — 3 HTMX tabs |
| `inventory/templates/inventory/product/form.html` | **Rewrite** |
| `inventory/templates/inventory/product/partials/_overview.html` | **Rewrite** |
| `inventory/templates/inventory/product/partials/_transaction.html` | **Rewrite** |
| `inventory/templates/inventory/product/partials/_status_change.html` | **Rewrite** |
| `inventory/templates/inventory/inventory/inventory.html` | **Rewrite** |
| `inventory/templates/inventory/inventory/inventory_transactions.html` | **Rewrite** |
| `inventory/templates/inventory/inventory/serialized_inventory.html` | **Rewrite** |
| `inventory/templates/inventory/inventory/inventory_adjusments.html` | **Rewrite** |

### Assembly Module (Task 34)

| File | Action |
|---|---|
| `inventory/templates/inventory/inventory/inventory_transformations.html` | **Rewrite** — jobs list |
| `inventory/templates/inventory/inventory/transformation_detail.html` | **Rewrite** — units table |
| `inventory/templates/inventory/inventory/transformation_form.html` | **Rewrite** — server-state formset |
| `inventory/templates/inventory/inventory/partials/transformation_item_form.html` | **Rewrite** — formset partial |

### Supply Chain Module (Tasks 35–38)

| File | Action |
|---|---|
| `supply_chain/templates/supply_chain/suppliers/supplier_list.html` | **Rewrite** |
| `supply_chain/templates/supply_chain/suppliers/supplier_detail.html` | **Rewrite** — POs + payments tabs |
| `supply_chain/templates/supply_chain/suppliers/form.html` | **Rewrite** — modal fragment |
| `supply_chain/templates/supply_chain/po/purchases.html` | **Rewrite** — list with filters |
| `supply_chain/templates/supply_chain/po/purchase_detail.html` | **Rewrite** — timeline layout |
| `supply_chain/templates/supply_chain/po/form.html` | **Rewrite** — server-state formset |
| `supply_chain/templates/supply_chain/po/partials/po_item_form_row.html` | **Replaced** by `_formset.html` |
| `supply_chain/templates/supply_chain/po/partials/error.html` | **Delete** — error display inline |
| `supply_chain/templates/supply_chain/payment_made/payment_list.html` | **Rewrite** |
| `supply_chain/templates/supply_chain/payment_made/payment_detail.html` | **Rewrite** |
| `supply_chain/templates/supply_chain/payment_made/form.html` | **Rewrite** — modal fragment |
| `supply_chain/templates/supply_chain/goods_receipts/receipts.html` | **Rewrite** |
| `supply_chain/templates/supply_chain/goods_receipts/receipt_detail.html` | **Rewrite** |
| `supply_chain/templates/supply_chain/goods_receipts/form.html` | **Rewrite** — server-state formset |
| `supply_chain/templates/supply_chain/goods_receipts/receipt_layers.html` | **Rewrite/merge** |
| `supply_chain/templates/supply_chain/goods_receipts/partials/receipt_item_form.html` | **Replaced** by `_formset.html` |

### New Pages (Task 39)

| File | Action |
|---|---|
| `account/templates/account/login.html` | **Create** — dark full-screen layout |
| `core/templates/core/audit_log.html` | **Create** — read-only table with filters |
| `core/templates/core/settings.html` | **Create** — 3 sections: business info, staff, thresholds |
| `core/templates/core/low_stock_detail.html` | **Create** — per-product cards with Create PO button |

---

## PHASE 3 TASK LIST

---

### Task 25 — Base templates and shared partials

**What to build:**

Write `templates/index.html` from scratch. Match the v4 prototype's structure,
fonts, and design tokens exactly:

```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>{% block title %}RMS{% endblock %}</title>
  <meta name="htmx-config" content='{"scrollIntoViewOnBoost": false}'>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;450;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=DM+Serif+Display&display=swap"
        rel="stylesheet">
  <link rel="stylesheet" href="{% static 'css/tailwind.css' %}">
  <link rel="stylesheet" href="{% static 'css/custom.css' %}">
  <style>
    /* Design tokens — match v4 prototype */
    :root {
      --color-bg: #f8fafc;
      --color-surface: #ffffff;
      --color-sidebar: #0f172a;
      --color-sidebar-hover: #1e293b;
      --color-sidebar-active: #1e293b;
      --color-border: #e2e8f0;
      --color-border-light: #f1f5f9;
      --color-text: #0f172a;
      --color-text-secondary: #64748b;
      --color-text-muted: #94a3b8;
      --color-brand: #d97706;
      --color-brand-hover: #b45309;
      --color-brand-light: #fff7ed;
      --color-success: #059669;
      --color-success-bg: #ecfdf5;
      --color-danger: #e11d48;
      --color-danger-bg: #fff1f2;
      --color-warning: #d97706;
      --color-warning-bg: #fffbeb;
      --color-info: #2563eb;
      --color-info-bg: #eff6ff;
      --shadow-sm: 0 1px 2px 0 rgb(15 23 42 / 0.04);
      --shadow-md: 0 4px 6px -1px rgb(15 23 42 / 0.05), 0 2px 4px -2px rgb(15 23 42 / 0.04);
      --shadow-lg: 0 10px 15px -3px rgb(15 23 42 / 0.06), 0 4px 6px -4px rgb(15 23 42 / 0.04);
      --shadow-xl: 0 20px 25px -5px rgb(15 23 42 / 0.06), 0 8px 10px -6px rgb(15 23 42 / 0.04);
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 16px;
      --radius-xl: 20px;
      --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
      --transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
      --transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);
    }
    * { font-family: 'Inter', system-ui, sans-serif; }
    .font-mono { font-family: 'IBM Plex Mono', monospace !important; }
    .amount { font-family: 'IBM Plex Mono', monospace; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
    html, body { height: 100%; }
    body { overflow: hidden; background: var(--color-bg); color: var(--color-text); -webkit-font-smoothing: antialiased; }
    #app { display: flex; height: 100vh; width: 100vw; }
  </style>
</head>
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>

  {# Mobile header — hidden on desktop, shown on mobile #}
  <div id="mobile-header" class="hidden max-md:flex sticky top-0 z-50 bg-white border-b border-slate-200 p-3 items-center gap-3">
    <button class="hamburger w-9 h-9 flex items-center justify-center rounded-lg text-slate-600 border border-slate-200 bg-white"
            onclick="document.getElementById('sidebar').classList.toggle('open'); document.getElementById('sidebar-overlay').classList.toggle('open')"
            aria-label="Open menu">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <div class="flex items-center gap-2.5">
      <div class="w-7 h-7 bg-brand-600 rounded-lg flex items-center justify-center">
        <span class="text-white text-xs font-bold">R</span>
      </div>
      <span class="font-semibold text-sm text-slate-800">RetailMS</span>
    </div>
  </div>

  <div id="app">
    {# Sidebar overlay for mobile #}
    <div id="sidebar-overlay" class="hidden fixed inset-0 bg-slate-950/50 z-40 backdrop-blur-sm"
         onclick="document.getElementById('sidebar').classList.remove('open'); this.classList.remove('open')"></div>

    {% include "partials/sidebar.html" %}

    <main id="main_body" class="flex-1 overflow-y-auto relative" style="background: var(--color-bg);">
      {% include "partials/spinner.html" with id="body_spinner" %}
      {% block content %}{% endblock %}
    </main>
  </div>

  <div id="modal_container"></div>
  {% include "partials/toast.html" %}

  <script src="{% static 'js/htmx.min.js' %}"></script>
  <script src="{% static 'js/app.js' %}"></script>
  {% block extra_js %}{% endblock %}
</body>
</html>
```

Sidebar active state — use Django's URL resolver, no JS needed:

```html
{# templates/partials/sidebar.html #}
{% load static %}
{% with url=request.resolver_match.url_name %}
<aside id="sidebar" class="w-[256px] flex-shrink-0 bg-slate-900 flex flex-col h-screen overflow-y-auto overflow-x-hidden border-r border-slate-800
       max-md:fixed max-md:left-0 max-md:top-0 max-md:z-50 max-md:transition-transform max-md:duration-300
       max-md:data-[open]:translate-x-0 max-md:-translate-x-full max-md:w-[280px] max-md:max-w-[85vw]">

  {# Logo #}
  <div class="px-5 py-5 border-b border-slate-800 flex-shrink-0">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 bg-brand-600 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
        <span class="text-white text-sm font-bold">R</span>
      </div>
      <div>
        <div class="text-white font-bold text-sm leading-tight tracking-tight">RetailMS</div>
        <div class="text-slate-500 text-[11px] font-medium">v2.0 · Lagos</div>
      </div>
    </div>
  </div>

  {# Navigation #}
  <nav class="flex-1 py-3 px-2.5 overflow-y-auto">
    <div class="text-[10px] font-bold text-slate-600 uppercase tracking-wider px-5 pb-1.5 pt-5">Overview</div>

    <a href="{% url 'dashboard' %}"
       hx-get="{% url 'dashboard' %}"
       hx-target="#main_body"
       hx-push-url="true"
       hx-indicator="#body_spinner"
       onclick="document.getElementById('sidebar').classList.remove('open'); document.getElementById('sidebar-overlay').classList.remove('open')"
       class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 mx-2.5 relative
              {% if url == 'dashboard' %}bg-slate-800 text-slate-50 font-semibold before:content-[''] before:absolute before:left-[-10px] before:top-2 before:bottom-2 before:w-[3px] before:bg-brand-600 before:rounded-r{% else %}text-slate-400 hover:bg-slate-800 hover:text-slate-200{% endif %}">
      <svg class="w-[18px] h-[18px] flex-shrink-0 {% if url == 'dashboard' %}text-brand-500{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
      Dashboard
    </a>

    <a href="{% url 'audit_log' %}"
       hx-get="{% url 'audit_log' %}"
       hx-target="#main_body"
       hx-push-url="true"
       hx-indicator="#body_spinner"
       class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 mx-2.5 relative
              {% if url == 'audit_log' %}bg-slate-800 text-slate-50 font-semibold before:content-[''] before:absolute before:left-[-10px] before:top-2 before:bottom-2 before:w-[3px] before:bg-brand-600 before:rounded-r{% else %}text-slate-400 hover:bg-slate-800 hover:text-slate-200{% endif %}">
      <svg class="w-[18px] h-[18px] flex-shrink-0 {% if url == 'audit_log' %}text-brand-500{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/></svg>
      Audit Log
    </a>

    <div class="text-[10px] font-bold text-slate-600 uppercase tracking-wider px-5 pb-1.5 pt-5">Customers</div>

    <a href="{% url 'customers' %}"
       hx-get="{% url 'customers' %}"
       hx-target="#main_body"
       hx-push-url="true"
       hx-indicator="#body_spinner"
       class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 mx-2.5 relative
              {% if url == 'customers' %}bg-slate-800 text-slate-50 font-semibold before:content-[''] before:absolute before:left-[-10px] before:top-2 before:bottom-2 before:w-[3px] before:bg-brand-600 before:rounded-r{% else %}text-slate-400 hover:bg-slate-800 hover:text-slate-200{% endif %}">
      <svg class="w-[18px] h-[18px] flex-shrink-0 {% if url == 'customers' %}text-brand-500{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
      Customers
    </a>

    <a href="{% url 'sales' %}"
       hx-get="{% url 'sales' %}"
       hx-target="#main_body"
       hx-push-url="true"
       hx-indicator="#body_spinner"
       class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 mx-2.5 relative
              {% if url == 'sales' %}bg-slate-800 text-slate-50 font-semibold before:content-[''] before:absolute before:left-[-10px] before:top-2 before:bottom-2 before:w-[3px] before:bg-brand-600 before:rounded-r{% else %}text-slate-400 hover:bg-slate-800 hover:text-slate-200{% endif %}">
      <svg class="w-[18px] h-[18px] flex-shrink-0 {% if url == 'sales' %}text-brand-500{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z"/></svg>
      Sales
    </a>

    <div class="text-[10px] font-bold text-slate-600 uppercase tracking-wider px-5 pb-1.5 pt-5">Inventory</div>

    <a href="{% url 'inventory' %}"
       hx-get="{% url 'inventory' %}"
       hx-target="#main_body"
       hx-push-url="true"
       hx-indicator="#body_spinner"
       class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 mx-2.5 relative
              {% if url == 'inventory' %}bg-slate-800 text-slate-50 font-semibold before:content-[''] before:absolute before:left-[-10px] before:top-2 before:bottom-2 before:w-[3px] before:bg-brand-600 before:rounded-r{% else %}text-slate-400 hover:bg-slate-800 hover:text-slate-200{% endif %}">
      <svg class="w-[18px] h-[18px] flex-shrink-0 {% if url == 'inventory' %}text-brand-500{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 10V11m0 0L4 7"/></svg>
      Inventory
    </a>

    <a href="{% url 'transformation_list' %}"
       hx-get="{% url 'transformation_list' %}"
       hx-target="#main_body"
       hx-push-url="true"
       hx-indicator="#body_spinner"
       class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 mx-2.5 relative
              {% if url == 'transformation_list' %}bg-slate-800 text-slate-50 font-semibold before:content-[''] before:absolute before:left-[-10px] before:top-2 before:bottom-2 before:w-[3px] before:bg-brand-600 before:rounded-r{% else %}text-slate-400 hover:bg-slate-800 hover:text-slate-200{% endif %}">
      <svg class="w-[18px] h-[18px] flex-shrink-0 {% if url == 'transformation_list' %}text-brand-500{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>
      Assembly Jobs
    </a>

    <div class="text-[10px] font-bold text-slate-600 uppercase tracking-wider px-5 pb-1.5 pt-5">Procurement</div>

    <a href="{% url 'po_list' %}"
       hx-get="{% url 'po_list' %}"
       hx-target="#main_body"
       hx-push-url="true"
       hx-indicator="#body_spinner"
       class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 mx-2.5 relative
              {% if url == 'po_list' %}bg-slate-800 text-slate-50 font-semibold before:content-[''] before:absolute before:left-[-10px] before:top-2 before:bottom-2 before:w-[3px] before:bg-brand-600 before:rounded-r{% else %}text-slate-400 hover:bg-slate-800 hover:text-slate-200{% endif %}">
      <svg class="w-[18px] h-[18px] flex-shrink-0 {% if url == 'po_list' %}text-brand-500{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
      Purchase Orders
    </a>

    <a href="{% url 'suppliers' %}"
       hx-get="{% url 'suppliers' %}"
       hx-target="#main_body"
       hx-push-url="true"
       hx-indicator="#body_spinner"
       class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 mx-2.5 relative
              {% if url == 'suppliers' %}bg-slate-800 text-slate-50 font-semibold before:content-[''] before:absolute before:left-[-10px] before:top-2 before:bottom-2 before:w-[3px] before:bg-brand-600 before:rounded-r{% else %}text-slate-400 hover:bg-slate-800 hover:text-slate-200{% endif %}">
      <svg class="w-[18px] h-[18px] flex-shrink-0 {% if url == 'suppliers' %}text-brand-500{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z"/></svg>
      Suppliers
    </a>

    <div class="text-[10px] font-bold text-slate-600 uppercase tracking-wider px-5 pb-1.5 pt-5">System</div>

    <a href="{% url 'settings' %}"
       hx-get="{% url 'settings' %}"
       hx-target="#main_body"
       hx-push-url="true"
       hx-indicator="#body_spinner"
       class="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-150 mx-2.5 relative
              {% if url == 'settings' %}bg-slate-800 text-slate-50 font-semibold before:content-[''] before:absolute before:left-[-10px] before:top-2 before:bottom-2 before:w-[3px] before:bg-brand-600 before:rounded-r{% else %}text-slate-400 hover:bg-slate-800 hover:text-slate-200{% endif %}">
      <svg class="w-[18px] h-[18px] flex-shrink-0 {% if url == 'settings' %}text-brand-500{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
      Settings
    </a>
  </nav>

  {# User area #}
  <div class="border-t border-slate-800 px-5 py-4 flex-shrink-0">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-full bg-brand-600 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
        {{ request.user.first_name|first|upper }}
      </div>
      <div class="flex-1 min-w-0">
        <div class="text-white text-sm font-semibold truncate">{{ request.user.get_full_name }}</div>
        <div class="text-slate-500 text-xs font-medium">{{ request.user.is_staff|yesno:"Admin,Staff" }}</div>
      </div>
      <a href="{% url 'logout' %}" title="Sign out"
         class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-all">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
      </a>
    </div>
  </div>

</aside>
{% endwith %}
```

**What to delete after this task completes:**
`overlay.html`, `mega_menu.html`, `plus_icon.html`, `htmx_preloader.html`,
`delete_toast.html`, `header.html`, `table_filter.html`

- Risk: HIGH — affects every page. Verify the app loads and navigation works before Task 26.
- Deliverable: App loads, sidebar renders, HTMX navigation works, modal container present.

---

### Task 26 — `app.js` and static file setup

**Write `static/js/app.js`** — this file replaces `bundle.js` and `formset.js`.
See `rms_phase3_addendum.md` Part 2 for the complete, canonical version. The file
must contain exactly these sections:

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

document.addEventListener('showMessages', function(e) {
  const messages = (e.detail && e.detail.value) ? e.detail.value : e.detail;
  if (Array.isArray(messages)) showMessages(messages);
});

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
    text: msg.text, icon: msg.icon || 'info', toast: true,
    position: 'top-end', showConfirmButton: false,
    timer: isError ? 0 : 4000, timerProgressBar: !isError,
    showCloseButton: true, customClass: { popup: 'swal-rms-popup' },
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

**What this file does NOT contain:**
- No `setWizardStep()` — wizard steps are server-driven via URLs
- No `init()` / `htmx:afterSwap` hooks — not needed
- No `selectItem()` — selection is via radio buttons and form submission
- No `addSaleItem()` — formsets use server-state pattern
- No `showToast()` — replaced by SweetAlert2 system above

**Copy HTMX to static:**
```bash
# Download htmx 2.x minified and place at:
static/js/htmx.min.js
```

**Delete:**
```bash
rm theme/static/js/dist/bundle.js
rm theme/static/js/formset.js   # or equivalent path
```

**Update `settings.py` STATICFILES_DIRS** if the path has changed from `theme/static`
to `static`. Verify `python manage.py collectstatic --dry-run` finds the files.

- Risk: Medium — losing the JS bundle breaks any page that used Alpine
  (but all those pages are being rewritten in Tasks 27–39, so this is acceptable)
- Deliverable: `app.js` exists, `htmx.min.js` exists, no console errors on any rebuilt page

---

### Task 27 — Dashboard

**Prototype section:** Dashboard page

**New view context additions** (update `core/views.py → dashboard()`):

```python
def dashboard(request):
    period = request.GET.get('period', 'month')
    # ... existing aggregations ...

    # New: attention alerts data
    LOW_STOCK_THRESHOLD = 5
    low_stock = Inventory.objects.filter(
        quantity__lte=LOW_STOCK_THRESHOLD, quantity__gt=0
    ).select_related('product')[:5]

    stockout = Inventory.objects.filter(quantity=0).select_related('product')[:5]

    pending_deliveries = PurchaseOrder.objects.filter(
        delivery_status__in=['pending', 'partially received']
    ).select_related('supplier')[:3]

    idle_balances = DepositAccount.objects.filter(
        cached_available_balance__gte=500000
    ).select_related('customer').order_by('-cached_available_balance')[:3]

    context = {
        # ... existing context ...
        'low_stock': low_stock,
        'stockout': stockout,
        'pending_deliveries': pending_deliveries,
        'idle_balances': idle_balances,
        'period': period,
    }
```

**Key template sections:**
- Attention alerts panel — 3-column grid, only shown when data exists
- KPIs — 4 stat cards, date-range aware
- Revenue bar chart — SVG with `last_7_days_revenue` context data
- Top products — horizontal bar chart with percentage fill
- Recent sales + recent deposits — two-column tables

**Date range filter:**
```html
<select hx-get="{% url 'dashboard' %}"
        hx-target="#main_body"
        hx-push-url="true"
        hx-trigger="change"
        name="period"
        class="field-select w-auto text-sm">
  <option value="month" {% if period == 'month' %}selected{% endif %}>This Month</option>
  <option value="last_month" {% if period == 'last_month' %}selected{% endif %}>Last Month</option>
  <option value="year" {% if period == 'year' %}selected{% endif %}>This Year</option>
</select>
```

- Deliverable: Dashboard loads with real data, date filter works, no chart errors

---

### Task 28 — Customers List

**Prototype section:** Customers list page

**New context** — add balance columns to the queryset:
```python
customers = Customer.objects.annotate(
    total_balance=F('depositaccount__cached_total_balance'),
    allocated_balance=F('depositaccount__cached_allocated_balance'),
    available_balance=F('depositaccount__cached_available_balance'),
    active_agreement_count=Count(
        'depositaccount__purchaseagreement',
        filter=Q(depositaccount__purchaseagreement__status='ACTIVE')
    ),
    sale_count=Count('sale'),
).select_related('depositaccount').order_by('full_name')
```

**Table columns:** Name + number | Total Deposited | Committed | Available | Agreements | CFA | Sales

**Empty state** — when no customers match search:
```html
{% empty %}
<tr><td colspan="7" class="py-16 text-center">
  <div class="text-slate-400 text-sm">No customers found matching "{{ q }}"</div>
</td></tr>
{% endfor %}
```

- Deliverable: Customer list with all 7 columns, search works via HTMX, empty state shows

---

### Task 29 — Customer Detail

**Prototype section:** Customer detail (financial summary + 4 tabs)

This is the most important and most visited page. Take extra care.

**Financial summary panel** uses `cached_*` fields from `DepositAccount`.
The allocation bar percentage is computed in the view:

```python
account = customer.depositaccount
total = account.cached_total_balance
allocated_pct = int((account.cached_allocated_balance / total * 100)) if total > 0 else 0
available_pct = 100 - allocated_pct
context['allocated_pct'] = allocated_pct
context['available_pct'] = available_pct
```

**Agreement progress bars** — add `fulfilled_quantity` and `fulfillment_percent`
as properties to `PurchaseAgreementLineItem`:

```python
@property
def fulfilled_quantity(self):
    from customer.models import BoxedSale, CoupledSale
    # Count across ALL versions of this line_number
    return (
        BoxedSale.objects.filter(
            agreement_line_item__line_number=self.line_number,
            agreement_line_item__purchase_agreement=self.purchase_agreement,
            sale__status='active',
        ).aggregate(total=Sum('quantity'))['total'] or 0
    ) + CoupledSale.objects.filter(
        agreement_line_item__line_number=self.line_number,
        agreement_line_item__purchase_agreement=self.purchase_agreement,
        sale__status='active',
    ).count()

@property
def fulfillment_percent(self):
    if self.quantity_ordered == 0:
        return 0
    return min(100, int(self.fulfilled_quantity / self.quantity_ordered * 100))
```

**Tab routing** via GET parameter:
```python
def customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.select_related('depositaccount'), pk=pk)
    active_tab = request.GET.get('tab', 'agreements')
    # ... build context ...
    if request.htmx and 'tab' in request.GET:
        # Return only the tab content partial
        return HttpResponse(
            render_to_string('customers/customer_detail.html#tab_content', context, request=request)
        )
    return render(request, 'customers/customer_detail.html', context)
```

**New modal views to add:**

```python
def modal_deposit(request, pk):           # GET — deposit form modal
def modal_new_agreement(request, pk):     # GET — new agreement modal
def modal_new_cfa(request, pk):           # GET — new CFA modal
def modal_new_customer(request):          # GET — new customer modal
```

- Deliverable: Financial summary shows correct live data, all 4 tabs load via HTMX,
  progress bars render, all modals open and submit correctly

---

### Task 30 — Agreement and CFA Forms (modals)

**Prototype sections:** New Agreement modal, New CFA modal, CFA disbursement modal

**Purchase Agreement modal** uses the server-state formset pattern.
The add/remove buttons send `hx-post` to the agreement creation view.

**CFA live preview** — two inputs trigger `updateCfaPreview()` from `app.js`:
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
       placeholder="e.g. 1800"
       oninput="updateCfaPreview(document.getElementById('id_amount_allocated'), this)">

{# Live preview panel #}
<div class="bg-brand-50 border border-brand-100 rounded-xl p-4 mt-3">
  <div class="flex justify-between text-sm mb-1">
    <span class="text-slate-500">Naira locked</span>
    <span id="cfa-naira-preview" class="amount font-medium">₦0</span>
  </div>
  <div class="flex justify-between text-sm border-t border-brand-100 pt-2 mt-2">
    <span class="font-medium text-slate-700">Expected CFA</span>
    <span id="cfa-xof-preview" class="amount font-semibold text-lg">0 XOF</span>
  </div>
  <div class="text-xs text-slate-400 mt-1">
    = (Naira ÷ rate) × 1,000, rounded to nearest 100 XOF
  </div>
</div>
```

**Balance validation** — show warning inline if total agreement value > available balance.
Compute in view when handling the HTMX formset manipulation requests.

- Deliverable: Both modals load, formsets add/remove rows, CFA preview updates live, balance warning shows

---

### Task 31 — Sales List and Sale Detail

**Prototype sections:** Sales list, Sale detail (active state), voided sale state

**Sale detail** — split from the list view. Each sale links to `/sales/<pk>/`.

**Void confirmation modal view** (new):
```python
def confirm_void_sale(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related(
            'boxedsale_set__product',
            'coupledsale_set__transformation_item',
        ),
        pk=pk
    )
    return render(request, 'customers/sales/modals/void_sale_confirm.html', {'sale': sale})
```

**After void POST** — return an HTMX redirect to the sale detail page:
```python
def void_sale_view(request, pk):
    void_reason = request.POST.get('void_reason', '')
    try:
        services.void_sale(pk, void_reason, request.user, request=request)
        messages.success(request, f'Sale voided. {void_reason}')
    except BusinessRuleViolation as e:
        messages.error(request, str(e))
    return HttpResponseClientRedirect(reverse('sale_detail', kwargs={'pk': pk}))
```

Use `HX-Redirect` response header or `django-htmx`'s `HttpResponseClientRedirect`.

- Deliverable: Sales list renders with filters, sale detail shows all info, void modal works end-to-end

---

### Task 32 — Sale Creation Wizard (4 steps)

**Prototype section:** Sale creation wizard

This is the most complex form. Break it into sub-tasks.

**32a — URL and view structure**

Add to `customer/urls.py`:
```python
path('sales/new/',         sale_wizard,         name='sale_create'),
path('sales/new/step2/',   sale_wizard_step2,   name='sale_step2'),
path('sales/new/step3/',   sale_wizard_step3,   name='sale_step3'),
path('sales/new/confirm/', sale_wizard_confirm, name='sale_confirm'),
path('sales/new/submit/',  sale_wizard_submit,  name='sale_submit'),
```

Each step returns only the next step's HTML. State passes forward as hidden inputs.
No session state — everything lives in the POST body.

Step indicator partial `partials/wizard_steps.html`:
```html
{% comment %}
  Takes: current_step (int 1-4), steps (list of {number, label})
{% endcomment %}
<div class="flex items-center gap-0 mb-8 overflow-x-auto">
  {% for step in steps %}
  <div class="flex items-center gap-2 flex-shrink-0">
    <div data-step="{{ step.number }}"
         class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold
                {% if step.number < current_step %}bg-emerald-500 text-white step-done
                {% elif step.number == current_step %}bg-brand-600 text-white step-current
                {% else %}bg-slate-100 text-slate-400 step-future{% endif %}">
      {% if step.number < current_step %}✓{% else %}{{ step.number }}{% endif %}
    </div>
    <span class="text-sm {% if step.number <= current_step %}font-medium text-slate-900{% else %}text-slate-400{% endif %}">
      {{ step.label }}
    </span>
  </div>
  {% if not forloop.last %}
  <div class="flex-1 min-w-6 h-px bg-slate-200 mx-3"></div>
  {% endif %}
  {% endfor %}
</div>
```

**32b — Step 3: Items (the formset step)**

Step 3 manages TWO formsets simultaneously — one for boxed items, one for coupled items.
The payment method (from step 2) determines which formset is active:
- `from deposit`: coupled and/or boxed items linked to agreement line items
- `bank transfer` / `cash`: free-form items with manual price entry

Each formset follows the canonical server-state pattern.
Boxed and coupled formsets have separate add/remove POST keys:
`add_row_boxed`, `remove_row_boxed`, `add_row_coupled`, `remove_row_coupled`

The step 3 view handles all four keys plus the "next" submission.

**32c — Step 4: Confirm**

Show the complete sale summary. The consequences panel is generated from the
form data passed as hidden inputs — not from the database (the sale hasn't been
saved yet at this point).

Final submit goes to `sale_wizard_submit` which calls `services.create_sale()`.

- Deliverable: Complete sale can be created end-to-end through all 4 steps.
  Deposit sales correctly filter products to agreement remaining quantities.
  Non-deposit sales allow free-form item entry.

---

### Task 33 — Inventory and Product Pages

**Prototype sections:** Inventory list, Product detail (3 tabs), Low stock detail

**New context for product detail:**
```python
product = get_object_or_404(Product, pk=pk)
context = {
    'product': product,
    'inventory': product.inventory,
    'transformation_items': TransformationItem.objects.filter(
        target_product=product
    ).select_related('transformation').order_by('-transformation__transformation_date'),
    'stock_history': InventoryTransaction.objects.filter(
        product=product
    ).order_by('-created_at')[:50],
    'avg_sale_price': ...,  # compute from BoxedSale and CoupledSale
    'active_tab': request.GET.get('tab', 'units'),
}
```

**New view for low stock detail** (add to `core/views.py`):
```python
def low_stock_detail(request):
    THRESHOLD = 5
    products = Inventory.objects.filter(
        quantity__lte=THRESHOLD
    ).select_related('product').order_by('quantity')
    return render(request, 'core/low_stock_detail.html', {
        'products': products,
        'threshold': THRESHOLD,
    })
```

Add to `core/urls.py`:
```python
path('low-stock/', low_stock_detail, name='low_stock_detail'),
```

- Deliverable: Inventory list with alert panel, product detail with 3 tabs, low stock page

---

### Task 34 — Assembly (Transformation) Pages

**Prototype sections:** Assembly jobs list, Assembly detail, New assembly form

**New assembly form** uses the canonical server-state formset pattern.
The transformation formset is `TransformationItemFormset`.

**Scan-ready field behaviour** — auto-advance from engine to chassis field.
Use event delegation in `app.js` (not inline `oninput`) so it works on
HTMX-appended rows:

```html
<input type="text"
       name="items-{{ forloop.counter0 }}-engine_number"
       class="scan-field scan-field-engine"
       placeholder="Scan or type ENG-XXXXX">
<input type="text"
       name="items-{{ forloop.counter0 }}-chassis_number"
       class="scan-field scan-field-chassis"
       placeholder="Scan or type CHN-XXXXX">
```

The `scan-field-engine` and `scan-field-chassis` classes are targeted by the
event delegation listener in `app.js` (see Task 26). No inline JS needed.

**Live cost basis display** — compute in view and pass to template:
The formset partial receives `source_wac` (current WAC of source product) and
`fee_per_unit` (total_fee / item_count). Display: `₦{{ source_wac|intcomma }} + ₦{{ fee_per_unit|intcomma }} = ₦{{ unit_cost|intcomma }}`.

The `fee_per_unit` updates whenever the total service fee changes — trigger via:
```html
<input type="number"
       name="service_fee"
       class="field-input font-mono"
       hx-post="{% url 'add_transformation' %}"
       hx-target="#formset-container"
       hx-swap="outerHTML"
       hx-include="closest form"
       hx-trigger="change"
       name="recalculate_fee">
```

- Deliverable: Assembly list, detail with units table, new assembly form with scan-ready fields

---

### Task 35 — Suppliers Pages

**Prototype sections:** Suppliers list, Supplier detail (2 tabs)

**Supplier detail tabs:** Purchase Orders | Payment History

**New context for supplier detail:**
```python
supplier = get_object_or_404(Supplier, pk=pk)
context = {
    'supplier': supplier,
    'purchase_orders': supplier.purchaseorder_set.select_related().order_by('-order_date'),
    'payments': Payment.objects.filter(
        purchase_order__supplier=supplier
    ).select_related('purchase_order').order_by('-payment_date'),
    'total_ordered_ytd': supplier.purchaseorder_set.filter(
        order_date__year=date.today().year
    ).aggregate(total=Sum('po_items__unit_price_at_order'))['total'] or 0,
    'open_po_count': supplier.purchaseorder_set.exclude(status='closed').count(),
    'active_tab': request.GET.get('tab', 'pos'),
}
```

New supplier modal: load via `hx-get` into `#modal_container`.

- Deliverable: Supplier list and detail render, PO and payment tabs work

---

### Task 36 — Purchase Orders (Timeline layout)

**Prototype sections:** PO list, PO detail (active timeline), PO closed state

**PO form** uses the canonical server-state formset pattern (full example given in
the Canonical Formset Pattern section above — implement it exactly).

**PO detail timeline** — see the timeline HTML in the previous protocol version —
it is correct and should be used as written. Key points:
- Each payment is a timeline event with amount, date, method, ref
- "Fully Paid" milestone appears when `po.payment_status == 'fulfilled'`
- "Awaiting Goods Receipt" step shows only when `po.delivery_status != 'received'`
- The "Record Receipt" button is visible only when `po.can_receive` is True
- The "Add Payment" button is visible on any non-closed PO

Both buttons open modals via `hx-get → #modal_container`.

- Deliverable: PO list with filters, PO detail timeline, both modal forms work, PO form with server-state formset

---

### Task 37 — Payments Pages

**Prototype section:** Record payment modal (primary entry from PO detail)

Payments in the new design are:
- **Created** from within the PO detail page (modal)
- **Viewed** on a standalone payment detail page (for audit)
- **Voided** via a confirmation modal from the payment detail page

Payment void modal must show whether the PO would re-open:
```html
{% if payment.purchase_order.status == 'closed' %}
<li class="font-semibold">• PO {{ payment.purchase_order.po_number }} will re-open</li>
{% endif %}
```

The payment list page remains accessible via the sidebar for staff who need to audit
all payments across suppliers.

- Deliverable: Payment modal works from PO detail, payment detail page renders, void works

---

### Task 38 — Goods Receipt Pages

**Prototype sections:** GR detail, GR void modal (blocked and unblocked states)

**GR form** uses the canonical server-state formset pattern.
The formset is `GoodsReceiptItemFormset`.

**GR detail** shows unit cost calculation per line:
```html
<div class="text-xs text-slate-400 mt-1">
  ₦{{ item.unit_price_at_receipt|intcomma }} (PO price)
  + ₦{{ item.allocated_delivery_cost_per_unit|intcomma }} (delivery)
  = <span class="amount font-medium text-slate-700">₦{{ item.unit_cost_at_receipt|intcomma }}</span>
</div>
```

**Void receipt modal** — check before showing:
```python
def confirm_void_receipt(request, pk):
    receipt = get_object_or_404(GoodsReceipt, pk=pk)
    can_void, reason = services.can_void_receipt(receipt)
    return render(request, 'supply_chain/goods_receipts/modals/void_receipt_confirm.html', {
        'receipt': receipt,
        'can_void': can_void,
        'block_reason': reason,
    })
```

If `can_void` is False, the modal shows the blocked state (red message, no confirm button).
If `can_void` is True, show the consequences list and confirm button.

- Deliverable: GR detail with cost breakdown, GR form with server-state formset, void modal correct

---

### Task 39 — New Pages

**39a — Login page**

Find the current login URL and view (likely `account/views.py` or Django's built-in).
Write `account/templates/account/login.html` — dark full-screen layout matching prototype.
No `{% extends 'index.html' %}` — this page has its own layout.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  ...Inter font, IBM Plex Mono, tailwind.css...
</head>
<body class="bg-slate-900 min-h-screen flex items-center justify-center">
  <div class="w-full max-w-sm mx-4">
    {# Logo, form, etc. from prototype #}
  </div>
</body>
</html>
```

**39b — Audit log page**

New view, URL, and template. Read-only table with filters.
Paginate at 50 per page. Filter by action, user, date range via HTMX list refresh pattern.

**39c — Settings page**

Three sections as separate cards:
1. Business Info — `BusinessConfig` singleton model (create if not exists)
2. Staff Accounts — list `CustomUser` objects with role badges
3. Stock Thresholds — per-product threshold configuration

`BusinessConfig` model (add to `core/models.py`):
```python
class BusinessConfig(models.Model):
    business_name = models.CharField(max_length=200, default='RMS')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    receipt_footer = models.TextField(blank=True)
    default_low_stock_threshold = models.PositiveIntegerField(default=5)

    class Meta:
        verbose_name = 'Business Configuration'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

**39d — Low stock detail page**
Implemented in Task 33 (view and URL). Template here:
Cards per product, showing stock level, threshold, and "Create PO" button that opens
the new PO modal pre-filtered to that product's supplier.

- Deliverable: All 4 pages accessible from sidebar and relevant links, all render without errors

---

### Task 40 — Final integration pass and cleanup

**40a — Delete all old templates that have been replaced**

After every task, the old template should already be deleted. This step is a final sweep:
```bash
# Verify no old templates remain alongside new ones
find . -name "*.html.bak" -o -name "*.html.old"
# Also check for any template that still uses Alpine (x-data, x-bind, @click)
grep -r "x-data\|x-bind\|@click\|x-show\|x-if" --include="*.html" .
```

**40b — Verify all URL names resolve**
```bash
python -c "
from django.test.utils import setup_test_environment
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mrms.settings')
django.setup()
from django.urls import reverse
urls = ['dashboard','customers','sales','inventory','transformation_list',
        'po_list','suppliers','audit_log','settings','low_stock_detail']
for u in urls:
    try: print(f'OK: {u} → {reverse(u)}')
    except Exception as e: print(f'FAIL: {u} → {e}')
"
```

**40c — Verify all HTMX targets exist**
```bash
grep -r "hx-target=" --include="*.html" . | grep -v modal_container | grep -v main_body \
  | grep -v tab_content | grep -v list_container | grep -v formset-container \
  | grep -v body_spinner
# Review any non-standard targets — they must exist in the template being targeted
```

**40d — End-to-end manual verification checklist**

For every page in the system:
- [ ] Full page load renders without error
- [ ] HTMX navigation from sidebar loads correctly
- [ ] Search/filter updates list without full reload
- [ ] Tab switching updates content without full reload
- [ ] All modals open from their trigger buttons
- [ ] All modal forms submit and update the page
- [ ] All void/cancel modals show plain-English consequences
- [ ] All amounts show ₦ prefix and intcomma formatting
- [ ] All reference numbers are font-mono
- [ ] Empty states render when lists are empty
- [ ] Error states render when form validation fails
- [ ] No Alpine.js `x-` attributes remain in any template
- [ ] No `bundle.js` or `formset.js` references remain

**40e — Run full test suite**
```bash
python manage.py test --verbosity=2
```

**40f — Build production Tailwind CSS**
```bash
./tailwindcss -i static/css/input.css -o static/css/tailwind.css --minify
```

Check the output CSS size. If it's unexpectedly small, some utility classes were
purged that are needed. Add them to the `safelist` in `tailwind.config.js`:
```javascript
module.exports = {
  content: ['./**/templates/**/*.html'],
  safelist: [
    // Dynamic classes that Tailwind can't detect statically
    'bg-emerald-50', 'text-emerald-700',  // badge classes
    'bg-brand-50', 'text-brand-700',
    'bg-blue-50', 'text-blue-700',
    'bg-rose-50', 'text-rose-700',
    { pattern: /pbar-fill/ },
    { pattern: /step-(done|current|future)/ },
    { pattern: /tl-dot/ },
  ],
  theme: { extend: {} },
  plugins: [],
}
```

- Deliverable: Clean codebase, all tests pass, production CSS built, no Alpine remnants

---

## PHASE 3 SUMMARY

| Task | Description | Approach | Risk |
|---|---|---|---|
| 25 | Base templates + shared partials | Rewrite from scratch | HIGH |
| 26 | `app.js` + static setup, delete `bundle.js` + `formset.js` | Write fresh | Low |
| 27 | Dashboard | Build from prototype | Medium |
| 28 | Customers list | Build from prototype | Low |
| 29 | Customer detail (financial summary + 4 HTMX tabs) | Build from prototype | HIGH |
| 30 | Agreement + CFA modals (server-state formset) | Build from prototype | Medium |
| 31 | Sales list + sale detail + void modal | Build from prototype | Medium |
| 32 | Sale creation wizard (4 steps, 2 formsets) | Build from prototype | HIGH |
| 33 | Inventory list + product detail + low stock page | Build from prototype | Medium |
| 34 | Assembly jobs list + detail + new assembly form | Build from prototype | Medium |
| 35 | Suppliers list + detail (2 tabs) | Build from prototype | Low-Medium |
| 36 | PO list + timeline detail + new PO form (server-state formset) | Build from prototype | Medium |
| 37 | Payments list + detail + void modal | Build from prototype | Low-Medium |
| 38 | Goods receipts + detail + void modal (server-state formset) | Build from prototype | Low-Medium |
| 39 | Login, audit log, settings, low stock detail (new pages) | Build from prototype | Low |
| 40 | Final integration pass, cleanup, production CSS | Verification + cleanup | Low |

**Total Phase 3 tasks: 16**
**Total project tasks: 40 (Tasks 1–10 Phase 1, 11–24 Phase 2, 25–40 Phase 3)**

**What this phase produces:**
- 0 lines of `formset.js` — replaced by server-state HTMX pattern
- 0 lines of Alpine.js — removed entirely
- 0 Select2 dropdowns — native selects throughout
- 1 canonical formset pattern applied to 6 forms
- 1 `app.js` under 60 lines covering all client-side needs
- Minimal partials — only when HTMX swap targets or reuse demands it
- Every page built directly from the prototype — no intermediate state, no double work
