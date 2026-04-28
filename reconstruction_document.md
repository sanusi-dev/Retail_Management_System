# RMS — Renovation Brief & Reconstruction Document (v2)
> Produced by direct codebase analysis of `github.com/sanusi-dev/Retail_Management_System`
> Updated with developer's confirmed architectural decisions and UI/UX direction
> Analyst: Claude Sonnet 4.6 | April 2026

---

## MISSION STATEMENT FOR THE AI WORKING ON THIS

This is NOT a rewrite. This is a **structured renovation** of an existing, working system with
correctly implemented domain logic. The backend solves a genuinely complex, niche business problem
— a deposit-funded purchase agreement system with serialised inventory and CFA forex allocation
for a Nigerian motorcycle distributor. That logic is largely correct and must be preserved.

The work has three layers, in strict priority order:
1. **Fix bugs and clean up the dependency stack** — make the system trustworthy
2. **Refactor toward an explicit service layer** — make the business logic testable and readable
3. **Redesign the UI/UX from scratch** — make the system feel as simple as the business expects

Do not generate "cleaner looking" alternatives to the domain logic without deep understanding of
why it was built that way. When in doubt, ask. The developer knows this domain better than you do.

---

## 1. SYSTEM OVERVIEW

**What it is:**
A desktop-first, browser-based Retail Management System purpose-built for a Nigerian
motorcycle/engine distributor that sells both direct and through a pre-funded customer deposit
model. The system manages the complete business cycle: procuring stock from suppliers, assembling
knocked-down units into serialised vehicles, selling them, and managing a complex internal
customer ledger that holds funds and locks them against future purchase or foreign-exchange
commitments.

**Who the users are:**
Authenticated staff only. Currently no role differentiation — all staff can perform all
operations. This must change (see Section 4). Accountability is maintained via `created_by` /
`updated_by` FK fields on every model.

**Business context:**
- Products: Motorcycles (Boxed = knocked-down kit, Coupled = assembled/serialised unit), Engines,
  Spare Parts
- Currency: Nigerian Naira (NGN / ₦) primary; CFA Franc (XOF) for agreements concering currency exchange which is also part of the service the business offer
- Operating model: Retail and wholesale — customers pre-fund large deposit accounts; sales are drawn
  against deposits via formal purchase agreements, and paid at point of sale if its not an agreement sale as there are two types of sales
- Cross-border: Customers allocate Naira to CFA agreements at locked exchange rates — the business facilitates FX for customers
- Deployment: Windows desktop application — Django + `waitress` WSGI server + SQLite, packaged
  as a zip with embedded Python. Offline-first by design. This is intentional and correct for the
  current use case.

---

## 2. DEPENDENCY DECISIONS (CONFIRMED BY DEVELOPER)

The current codebase has dependency bloat that adds complexity without value. The renovation must
clean this up. Here are the confirmed decisions:

### REMOVE these packages entirely

| Package | Reason |
|---|---|
| `django-tailwind` | Adds Node.js coupling, a `theme` app, a Procfile, and `tailwind start` process just to compile CSS. Replace with **Tailwind CSS standalone CLI**|
| `django-render-block` | Redundant — `django-template-partials` does the same job better. |
| `django-easy-audit` | Over-engineered for the need. Replace with a custom lightweight `AuditLog` model (see Section 6). |
| `django-browser-reload` | Dev convenience only, not needed in the project dependencies. |
| `django-environ` | Standard `os.environ` or `python-decouple` is sufficient. |
| `django-extensions` | Not used meaningfully in this project. |

### KEEP these packages

| Package | Reason |
|---|---|
| `django-htmx` | Core to the frontend architecture. Keep. |
| `django-template-partials` | Replaces `django-render-block`. Will be Django 6 core — using it now is forward-compatible. |
| `django-widget-tweaks` | Useful for form rendering in templates without custom widgets. |
| `django-debug-toolbar` | Keep for performance profiling — page load analysis during development. |
| `waitress` | Production WSGI server for the desktop app packaging. |
| `Tailwind CSS` | Keep the CSS framework, remove the Django wrapper package. Use standalone CLI. |

### Target `requirements.txt` after cleanup

```
Django>=6
django-htmx
django-widget-tweaks
waitress
python-decouple
```

Dev-only (`requirements-dev.txt`):
```
django-debug-toolbar
Faker
django-stubs
djlint
```

---

## 3. TECH STACK (TARGET)

| Layer | Current | Target |
|---|---|---|
| Language | Python 3.x | Python 3.12+ |
| Backend framework | Django 6.0 | Django 5.2.x (keep) |
| Frontend | Django Templates + HTMX | Django Templates + HTMX (keep, redesign templates) |
| CSS | Tailwind via `django-tailwind` | Tailwind CSS via standalone CLI |
| Database | SQLite3 | **PostgreSQL** (see rationale below) |
| ORM | Django ORM | Django ORM (keep) |
| Auth | Django sessions + CustomUser | Keep — add Group-based RBAC |
| Audit | `django-easy-audit` (disabled) | Custom `AuditLog` model with explicit service calls |
| Template partials | `django-render-block` | `django-template-partials` |
| Forms | Django Formsets + widget-tweaks | Keep |
| WSGI | `waitress` | Keep |
| PDF export | None | `WeasyPrint` or `xhtml2pdf` |
| Excel export | None | `openpyxl` |

**On the database decision:**
SQLite is intentional for the desktop-local deployment and is not inherently wrong. However, even
in a single-user desktop scenario, PostgreSQL provides proper `SELECT FOR UPDATE` locking semantics
that SQLite handles inconsistently. Given the financial nature of this system (balance reads before
writes, concurrent signal firing), PostgreSQL eliminates an entire class of potential data
corruption bugs. A local PostgreSQL install is straightforward on Windows. If PostgreSQL is ruled
out for packaging reasons, SQLite must be used in WAL mode with `PRAGMA journal_mode=WAL` and all
balance read-modify-write operations must use explicit transactions.

---

## 4. ARCHITECTURE: APP STRUCTURE (KEEP AS-IS)

The modular Django app structure is correct. Do not consolidate or restructure apps.

- `account` — CustomUser model and authentication views
- `inventory` — Products, brands, stock ledger, transformations
- `supply_chain` — Suppliers, purchase orders, payments to suppliers, goods receipts
- `customer` — Customers, deposit accounts, transactions, agreements, CFA agreements, sales
- `loan` — Loan module (currently a stub — see Section 10)
- `core` — Dashboard, shared context processors, utilities
- `theme` — Static assets (to be simplified — remove Node dependency)

---

## 5. ARCHITECTURE: SERVICE LAYER (CRITICAL REFACTOR)

**This is the most important backend change.**

Currently, business logic is split across three places: `model.clean()`, `model.save()`, and
Django signals. This makes the code hard to test, hard to trace, and produces surprising behaviour
when signals fire unexpectedly (e.g., during admin bulk actions or management commands).

**The target pattern:**

```
views.py  →  services.py  →  models.py
```

Views should only handle HTTP concerns (parse request, call service, return response). All
business logic — including what currently lives in signals — should move into explicit service
functions in `services.py` per app.

**Service functions to create (examples — not exhaustive):**

`inventory/services.py`:
- `process_transformation(form, formset, user)` ← already exists, keep
- `void_transformation(transformation_id, user)` ← already exists, keep
- `decrement_stock(product, quantity, source, user)` ← extract from signal
- `increment_stock(product, quantity, source, cost_per_unit, user)` ← extract from signal

`supply_chain/services.py`:
- `process_purchase_order(form, formset, user)` ← already exists, keep
- `process_goods_receipt(form, formset, user)` ← already exists, keep
- `void_receipt(receipt_id, user)` ← already exists, keep
- `record_supplier_payment(po, amount, method, user)`
- `void_supplier_payment(payment_id, user)`

`customer/services.py`:
- `record_deposit(account, amount, note, user)`
- `void_deposit(transaction_id, user)`
- `create_purchase_agreement(account, line_items, user)`
- `cancel_agreement(agreement_id, user)`
- `create_cfa_agreement(account, amount, rate, user)`
- `record_cfa_fulfillment(agreement_id, cfa_amount, notes, user)`
- `void_cfa_fulfillment(fulfillment_id, user)`
- `create_sale(customer, payment_method, agreement, items, user)`
- `void_sale(sale_id, user)`

**Signals should become thin wrappers or be removed entirely.** If a signal currently does
non-trivial work (e.g., the `process_sale_void_effects` signal which does inventory restoration,
status resets, AND financial refunds), that logic moves to a service function and the view calls
it explicitly. The signal becomes a single-line call to the service, or the signal is removed and
views call services directly.

**Exception handling in services:**
Services should raise explicit exceptions (`ValidationError`, custom `InsufficientFundsError`,
`InsufficientStockError`) that views catch and convert to user-facing messages. No bare
`except Exception: print(...)`.

---

## 6. AUDIT LOGGING (REPLACING django-easy-audit)

Replace `django-easy-audit` with a simple custom model. Only audit high-value, irreversible or
financially significant actions — not every ORM operation.

```python
# core/models.py
class AuditLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)  # e.g. "void_sale", "cancel_agreement"
    object_type = models.CharField(max_length=100)  # e.g. "Sale", "PurchaseAgreement"
    object_id = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=255)  # human-readable at time of action
    detail = models.JSONField(default=dict)  # any extra context
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
```

**Actions that MUST be audited:**
- Void sale
- Void goods receipt
- Void supplier payment
- Cancel purchase agreement
- Cancel CFA agreement
- Void customer deposit transaction
- Void transformation
- Any manual withdrawal from customer deposit
- User login / logout (use Django's built-in `user_logged_in` signal)

Service functions call `AuditLog.objects.create(...)` explicitly. No magic, no signals for audit.

---

## 7. DATA MODEL

The data model is fundamentally correct. Do not redesign it. Apply targeted fixes only.

### Domain: Inventory

**`Brand`** — No changes needed.
- `brand_id` (UUID PK), `name` (unique)

**`Product`** — No changes needed.
- `product_id` (UUID PK), `sku` (auto `{modelname}-{type_variant}`), `brand` → Brand, `modelname`,
  `category` (`motorcycle` | `engine` | `spare part`), `type_variant` (`boxed` | `coupled`),
  `description`, `base_product` (self-FK, Coupled only), `status`
- Rule: Coupled MUST have `base_product`. Boxed MUST NOT.
- Signal: Creating a Boxed Motorcycle auto-creates its Coupled counterpart. Keep this signal — it
  is simple, predictable, and correct.
- Signal: Auto-create `Inventory` record on product creation. Keep.

**`Inventory`** — No structural changes. WAC recalculation logic moves to service.
- `quantity` (PositiveInteger), `weighted_average_cost` (Decimal)
- WAC formula: `new_wac = (old_qty × old_wac + received_qty × unit_cost) / new_qty`

**`InventoryTransaction`** — No changes. Immutable audit ledger.
- `transaction_type`: `receipt` | `sale` | `transformation` | `*_reversal` variants
- `quantity_change` (signed), `cost_impact` (Decimal), `source` (Generic FK)

**`Transformation`** — No changes.
- `transformation_number`, `service_fee` (total for batch), `transformation_date`, `status`

**`TransformationItem`** — No changes to model. Inventory decrement moves to service.
- `engine_number` (unique), `chassis_number` (unique) — ADD: format validation (min length,
  alphanumeric constraint)
- `allocated_service_fee` (service_fee / item count), `unit_cost_at_transformation`
- `status`: `available` | `sold` | `reserved` | `voided`

---

### Domain: Supply Chain

**`Supplier`** — No changes.

**`PurchaseOrder`** — No changes to model.
- `po_number`, `delivery_status`, `payment_status`, `status`
- Status update methods stay on model as helpers, called from services.

**`PurchaseOrderItem`** — No changes.

**`Payment`** — FIX REQUIRED.
- Remove the duplicate `can_void` property definition. The correct logic:
  A payment CAN be voided if: status is PAID, AND the PO has not yet had any goods received
  (delivery_status == PENDING), AND the PO is not CLOSED.
- Move void logic to `supply_chain/services.void_supplier_payment()`

**`GoodsReceipt`** — No changes. `clean()` rule (must be fully paid before receiving) stays.

**`GoodsReceiptItem`** — No changes to model. WAC update and inventory increment move to service.
- `allocated_delivery_cost_per_unit`, `unit_cost_at_receipt`, `reverses` (self-FK for reversals)

---

### Domain: Customer & Finance

**`Customer`** — ADD fields:
- `email` (optional, EmailField)
- `address` (optional, TextField)
- Keep: `customer_number` (auto `CUST-`), `full_name` (unique), `phone`
- Signal: auto-create `DepositAccount` on customer creation. Keep — simple and correct.

**`DepositAccount`** — TARGETED FIX to cache invalidation.
- Keep the cached balance fields (`cached_total_balance`, `cached_allocated_balance`,
  `cached_available_balance`) — the caching approach is a valid performance optimisation.
- FIX: `update_cached_balances()` must not swallow exceptions silently. Raise or log to a real
  logger, not `print()`. If the cache update fails, the transaction that triggered it should fail
  too — use `transaction.atomic()` wrapping both the original save and the cache update.
- The balance calculation methods (`_calculate_total_balance()`, `_calculate_allocated_balance()`
  etc.) are correct. Do not rewrite them.

**`Transaction`** — No changes to model or `clean()` logic.
- FIX: In `clean()`, the available balance check must happen inside a `select_for_update()` lock
  to prevent race conditions if this ever runs concurrently.
- Types: `deposit` | `withdrawal` | `fulfillment` | `refund`
- Immutability rules (amount and type cannot change after creation) are correct. Keep.
- Rules blocking manual void of fulfillment/refund transactions are correct. Keep.

**`PurchaseAgreement`** — No changes.
- Status lifecycle: `ACTIVE` → `PARTIALLY_FULFILLED` → `FULFILLED` | `CANCELLED`
- `can_edit`: True only if zero fulfillments. Correct.
- `can_cancel`: True only if ACTIVE. Correct.

**`PurchaseAgreementLineItem`** — No changes. The versioning design is correct and intentional.
- `remaining_quantity` counting across ALL historical versions of a `line_number` is correct —
  prevents double-fulfillment after amendments. Do not simplify this.
- `line_number` + `version` + `is_current_version` + `superseded_by` versioning chain — keep.

**`CfaAgreement`** — No changes.
- `exchange_rate` stored as "Naira per XOF 1,000" (e.g., 1800 = ₦1.80 per XOF). This encoding
  is non-standard — ADD UI label clarification and input range validation (e.g., 500–5000) to
  prevent entry errors.
- FULFILLED when `remaining_cfa ≤ 100 XOF` epsilon. Correct — handles rounding on large amounts.

**`CfaFulfillment`** — No changes.

**`Sale`** — No changes to model or validation logic.
- `payment_method` ↔ `agreement` coupling rules are correct. Keep.
- ADD: `void_reason` field (TextField, optional) — record why a sale was voided.

**`CoupledSale`** — No changes. Price auto-set from agreement line item on deposit sales. Correct.

**`BoxedSale`** — No changes. Stock check and over-fulfillment check in `clean()` are correct.

---

### Domain: Loan (Stub — Needs Design Decision)

The Loan module exists as models only. Before any code is written here, the business logic must
be defined. Current model has:
- `Loan`: `loan_type` (`sales loan` | `normal loan`), `customer`, `principal_amount`,
  `loan_date`, `due_date`, `status`
- `LoanRepayments`: `loan`, `amount`, `payment_method`, `trxn_ref`, `remark`

**FIX immediately (even before feature is built):**
- `Loan.__str__` returns `self.loan_id` (UUID object) — change to `return str(self.loan_id)` or
  a meaningful string representation.
- Uncomment and complete the Meta constraints.
- Decide: is the Sale FK needed for Sales Loans? If yes, uncomment and implement.

**Open questions before building (see Section 12).**

---

## 8. BUSINESS RULES (PRESERVE ALL OF THESE)

These rules are correctly implemented and must survive the renovation unchanged.

| Rule | Location in current code |
|---|---|
| Stock cannot go below zero on sale | `BoxedSale.clean()` |
| Stock cannot go below zero on transformation | Signal on `TransformationItem` post_save |
| Goods receipt requires full PO payment first | `GoodsReceipt.clean()` |
| Deposit payment method requires a linked agreement | `Sale.clean()` |
| Agreement and customer must match | `Sale.clean()` |
| CoupledSale price auto-set from agreement (not editable) | `CoupledSale.save()` |
| BoxedSale price auto-set from agreement (not editable) | `BoxedSale.save()` |
| Cannot sell more than remaining agreement quantity | `BoxedSale.clean()` + `CoupledSale.clean()` |
| Cannot void deposit if funds are in active agreements | `Transaction.clean()` |
| Cannot manually void fulfillment/refund transactions | `Transaction.clean()` |
| Amount and type immutable after transaction creation | `Transaction.clean()` |
| Coupled products must have a base product | `Product.save()` |
| Boxed products must not have a base product | `Product.save()` |
| Transformation void only if all items still AVAILABLE | `inventory/services.can_void_transformation()` |
| Receipt void only if stock ≥ received quantity | `supply_chain/services.can_void_receipt()` |
| Cannot delete PurchaseAgreement with linked Sales | `pre_delete` signal |
| WAC recalculated on every receipt | Signal on `GoodsReceiptItem` post_save |
| Service fee split equally across transformation items | `inventory/services.process_transformation()` |
| CFA fulfillment cannot exceed remaining CFA | `CfaFulfillment.clean()` |
| CFA agreement requires available_balance ≥ allocated | `CfaAgreement.clean()` |
| CFA FULFILLED when remaining ≤ 100 XOF epsilon | `CfaAgreement.update_status()` |
| Remaining qty counts fulfillments across all line versions | `PurchaseAgreementLineItem.remaining_quantity` |

---

## 9. UI/UX REDESIGN (CRITICAL — THIS IS WHERE THE BIGGEST VALUE IS)

**The core problem with the current UI:**
The interface exposes the data model rather than the workflow. A user sees tables of
`PurchaseAgreementLineItems` when they should see "Alhaji Musa has ₦2.4M deposited, ₦1.8M
committed to 4 motorcycles, ₦600K free to use." The backend correctly solves a complex problem.
The UI must make that complexity invisible.

**Design principle for every screen:**
> "What is the user trying to accomplish right now, and is that the most obvious thing on the page?"

The current screens are built view-by-view, feature-by-feature. The redesign must be built
workflow-by-workflow, user-goal-by-user-goal.

---

### Dashboard

**Current:** KPI cards + charts + recent tables. Data-first layout.

**Target:** Action-first layout.
- The first thing a staff member sees should be: what needs attention today?
- Prioritise: low stock alerts, pending deliveries, agreements near fulfilment, large available
  balances sitting idle
- KPIs still present but secondary — the dashboard should feel like a morning briefing, not a
  data report
- Revenue trend, gross profit, inventory value — keep but de-emphasise relative to action items
- Date range selector on dashboard (currently hardcoded to current month)

---

### Customer Pages

**Current:** Customer list → Customer detail with sub-tabs (transactions, agreements, CFA, sales).
Data tables on each tab.

**Target: Customer detail must tell a story.**

The customer detail page is the most used page in the system. It should answer in 3 seconds:
- How much does this customer have with us? (total deposited)
- How much is committed? (allocated to agreements)
- How much is free? (available)
- What are they waiting for? (unfulfilled agreement items)
- What have we done for them recently? (recent sales)

**Financial summary panel (top of customer page):**
```
┌─────────────────────────────────────────────────────┐
│  ALHAJI MUSA IBRAHIM          CUST-4A2B             │
│                                                     │
│  Total Deposited      ₦4,200,000                   │
│  Committed            ₦3,600,000  (to 3 agreements)│
│  Available            ₦600,000    ✓ Free to use    │
└─────────────────────────────────────────────────────┘
```

Then below: agreements as visual progress bars (not tables), showing % fulfilled.

**Agreement view:**
Instead of "PurchaseAgreementLineItem" tables, show:
```
Agreement PUR-A1B2 | Created 12 Jan 2025
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TVS Apache 200 (Boxed)     3 of 5 delivered    ██████░░░░  60%
Honda CB125 (Coupled)      1 of 2 delivered    █████░░░░░  50%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: ₦2,250,000   Fulfilled: ₦1,350,000   Remaining: ₦900,000
```

**CFA Agreement view:**
```
CFA Agreement CFA-3C4D | ₦500,000 allocated at ₦1,800/1,000 XOF
Expected: 277,800 XOF
Disbursed: 150,000 XOF  ████████░░░░░░░░  54%
Remaining: 127,800 XOF
```

---

### Sale Creation Flow

**Current:** Form with dropdowns, formsets, multiple steps that require understanding the data model.

**Target:** Guided, wizard-style flow with clear decision points.

Step 1: Select customer
Step 2: Choose payment type ("From Deposit" vs "Direct Payment")
  → If "From Deposit": show customer's active agreements with remaining items visually
  → If "Direct Payment": show standard product selector
Step 3: Add items (one at a time with clear confirmation of stock availability)
Step 4: Review summary before confirming

The sale creation flow should never show the word "PurchaseAgreementLineItem" to the user.
It should say "Commit from Agreement" or "Apply to Alhaji Musa's Jan Agreement."

---

### Transformation (Assembly) Flow

**Current:** Form with engine/chassis number fields.

**Target:** Make serialisation feel deliberate and tactile.
- Clear indication of how many boxed units will be consumed
- Engine and chassis number fields should support barcode scanner input (cursor moves to next
  field automatically after entry — use `hx-trigger="change"` or Alpine.js autofocus)
- Show live preview of the assembled unit before saving
- After transformation, show a printable assembly record

---

### Procurement Flow (Purchase Orders)

**Current:** PO list → PO detail with payments and receipts as sub-sections.

**Target:** PO detail as a clear status timeline.
```
  PO-ABC123  |  Jincheng Motors  |  ₦2,100,000
  ─────────────────────────────────────────────
  ✓  Order Created       Jan 10
  ✓  Payment 1: ₦1,000,000   Jan 12  (Transfer)
  ✓  Payment 2: ₦1,100,000   Jan 15  (Transfer)
  ✓  Fully Paid
  ✓  Goods Received       Jan 22
  ✓  CLOSED
```

Payments and receipts integrated into the timeline, not separate sub-tables.

---

### General UI Principles

- **No raw reference numbers in primary displays.** Show `Alhaji Musa - 3 motorcycles pending`
  not `PUR-A1B2C3D4`.
- **Status badges must be actionable.** "PARTIALLY_FULFILLED" badge should link directly to the
  action to continue fulfilling.
- **Destructive actions** (void, cancel) must show a confirmation modal that explains the
  consequence in plain English, not just "Are you sure?"
  e.g. "Voiding this sale will: restore 2 units to stock, refund ₦900,000 to Alhaji Musa's
  deposit account, and unlock those items in his agreement."
- **Forms should show context**, not just fields. When adding a sale item from an agreement,
  show the agreement's remaining balance and remaining quantity next to the form.
- **Naira amounts always formatted** with ₦ prefix and comma separators. Never show raw numbers.
- **Consistency**: All list pages follow the same pattern — search bar top left, filter/sort top
  right, action button top right, paginated table below.
- **Mobile-aware** even if not mobile-first — the system is desktop-local but staff may use
  tablets. Tailwind responsive classes should be applied throughout.

---

### HTMX Patterns to Standardise

The current HTMX usage is good but inconsistent between modules. Standardise on:

- `hx-target="#main_body"` + `hx-push-url="true"` for full page navigations
- `hx-target="#modal_container"` for modal opens
- `hx-target="closest tr"` or `hx-target="closest .card"` for inline updates
- OOB toast via the existing `HtmxMessageMiddleware` — keep this pattern
- Use `hx-confirm` only for low-stakes confirmations. For destructive financial actions, load a
  proper confirmation modal (not a browser `confirm()` dialog) that shows the consequences.

---

## 10. BUGS TO FIX (IN ORDER OF SEVERITY)

| # | Bug | File | Fix |
|---|---|---|---|
| 1 | `Payment.can_void` defined twice | `supply_chain/models.py` | Remove second definition. Correct logic: can void if status=PAID AND delivery_status=PENDING AND PO not CLOSED |
| 2 | `Loan.__str__` returns UUID object | `loan/models.py` | Change to `return str(self.loan_id)` |
| 3 | Easy-audit watch flags all False | `mrms/settings.py` | Remove easy-audit entirely, implement custom AuditLog |
| 4 | Balance cache exceptions swallowed | `customer/signals.py` | Use proper logging + ensure cache failure fails the parent transaction |
| 5 | No `select_for_update()` in `Transaction.clean()` | `customer/models.py` | Wrap balance read in `select_for_update()` |
| 6 | Dashboard gross profit uses current WAC | `core/views.py` | For coupled sales use `unit_cost_at_transformation` (already done). For boxed sales, store cost at time of sale or accept the approximation and label it clearly in UI |
| 7 | Loan Meta constraints commented out | `loan/models.py` | Uncomment and complete once loan business logic is defined |

---

## 11. NEW FEATURES TO ADD

Prioritised by business value:

**High priority:**
- PDF receipt generation for sales (show customer, items, amounts, agreement reference)
- PDF for CFA fulfillment records (disbursement confirmation)
- Dashboard date range filter (currently hardcoded to current month/year)
- Customer email field + basic email receipt on sale confirmation
- Formal audit log viewer in UI (view AuditLog records filtered by user, action, date)

**Medium priority:**
- RBAC: Staff roles — at minimum `Admin`, `Sales`, `Warehouse`, `Finance`. Use Django Groups.
  - Sales: can create sales, view customers, view inventory
  - Warehouse: can process transformations and goods receipts, cannot access financials
  - Finance: can manage deposits, agreements, CFA — cannot void receipts
  - Admin: full access
- CSV/Excel export for: transaction history per customer, sales by period, inventory valuation
- Barcode scanner support on transformation and sale entry (auto-advance field on input, validate
  format)
- Low stock threshold configuration + alerts on dashboard

**Lower priority (define before building):**
- Loan module full implementation (requires stakeholder input — see Section 12)
- Multi-branch/location support (requires data model addition of `Location` entity)

---

## 12. OPEN QUESTIONS (MUST BE ANSWERED BEFORE CODING THOSE FEATURES)

1. **Loan module**: What is a "Sales Loan" vs "Normal Loan" in business terms? Does a Sales Loan
   fund a specific sale (buy now, pay later model)? Can a customer have both a deposit account
   and an active loan simultaneously? What is the repayment schedule model?

2. **CFA Agreements**: Who physically disburses the CFA? Is the business the FX dealer or an
   agent? Does each CfaFulfillment need a bank transfer reference number attached?

3. **Multi-branch**: Is there a plan to operate from multiple locations? If yes, `Inventory`,
   `Transformation`, and `GoodsReceipt` all need a `Location` FK added now.

4. **Barcode scanners**: Are barcode scanners used for chassis/engine number entry today (keyboard
   wedge mode), or is everything typed manually? If scanners are used, what format do the
   barcodes encode?

5. **Payment gateway**: Any plan to auto-reconcile customer deposits via Paystack/Flutterwave
   bank transfer notifications? This would replace manual deposit entry.

6. **WAC vs historical COGS**: Should boxed sale profitability on the dashboard use current WAC
   or WAC at the time of the sale? For accurate profit reporting, the WAC at time of sale should
   be stored on `BoxedSale` (as `unit_cost_at_sale` similar to how `CoupledSale` uses
   `unit_cost_at_transformation`).

7. **Agreement price lock**: If market prices rise after an agreement is signed, is the agreed
   price always honoured? Are there any conditions under which an agreement price can be
   renegotiated (this would be the amendment/versioning flow)?

8. **CFA rate validation**: Should the UI enforce a plausible range for the exchange rate field
   to prevent data entry errors? What is a realistic min/max for Naira per 1,000 XOF?

9. **Customer uniqueness**: `full_name` is currently the unique identifier for customers. Is this
   robust enough? Should a phone number or business registration number be the true unique key?

10. **Deployment target**: Is the system staying as a Windows desktop app, or is there a plan to
    move to a networked/web deployment? This affects whether PostgreSQL local install is feasible
    and whether multi-user concurrency needs to be fully solved.

---

## 13. WHAT NOT TO CHANGE

This section exists to protect correct, working decisions from being "improved" unnecessarily.

- **The deposit ledger design** (total / allocated / available balance split) — correct. Keep.
- **`PurchaseAgreementLineItem` versioning** — the `remaining_quantity` spanning all historical
  versions is intentional and prevents a real financial loophole. Do not simplify.
- **CFA epsilon tolerance** (100 XOF) for FULFILLED status — handles rounding on large amounts.
  Keep.
- **WAC formula** — standard weighted moving average cost accounting. Keep.
- **Transformation serialisation** (engine_number + chassis_number per item) — core to the
  business. Keep.
- **The HTMX + Django Templates stack** — do not add React, Vue, or any other JS framework.
- **`created_by` / `updated_by` fields on every model** — accountability trail. Keep.
- **UUID primary keys** — keep for all models. Avoids enumerable IDs in URLs.
- **`select_for_update()` on inventory decrements** — correct. Expand to balance operations too.
- **The `HtmxMessageMiddleware`** toast pattern — clean and correct. Keep.
- **Auto-creation signals** (deposit account on customer create, coupled product on boxed create,
  inventory record on product create) — these are simple, predictable, and correct. Keep as
  signals.