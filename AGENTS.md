# AGENTS.md — Retail Management System

## Project Overview

Django 6 app (project: `mrms`) for retail motorcycle/dealer management. SQLite backend, Tailwind CSS + HTMX + Alpine.js frontend. Custom user model (`account.CustomUser`). Time zone: `Africa/Lagos`.

## Dev Setup

```bash
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
npm install
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver            # terminal 1
npm run watch:css                     # terminal 2 (or: npm run dev)
```

Tailwind input is `static/css/input.css`; output goes to `static/css/tailwind.css`. The `build:css` script produces minified output.

Environment config uses `python-decouple` (`mrms/settings.py:8-9`). Requires `.env` with `SECRET_KEY` and `DEBUG`.

Whitenoise is configured for static file serving. Run `python manage.py collectstatic` before production.

## Running Tests

```bash
python manage.py test                          # all apps
python manage.py test customer                  # single app
python manage.py test customer.tests.test_financial_logic   # single module
python manage.py test inventory.tests.test_stock_display     # single test class
```

No pytest config — uses Django's built-in test runner. Tests live in `customer/tests/` and `inventory/tests/` (app-level `tests/` packages), or `tests.py` at app root for other apps (`supply_chain`, `core`, `loan`).

Dev dependencies include `Faker` (test factories), `djlint` (template linting), and `django-stubs` (type checking).

## Key Commands

```bash
python manage.py populate_cached_balances        # rebuild DepositAccount cache
python manage.py verify_cached_balances           # audit cache vs calculated
djlint --lint inventory/templates/                # template linting
```

## Architecture

### Django Apps & URL Prefixes

| App | URL Prefix | Purpose |
|-----|-----------|---------|
| `account` | `/` (empty) | Auth, CustomUser |
| `core` | `/` (dashboard) | Dashboard, AuditLog, shared utils |
| `customer` | `/customer/` | Customers, DepositAccounts, Transactions, PurchaseAgreements, CFA, Sales |
| `inventory` | `/inventory/` | Products, Brands, Inventory, Transformations |
| `loan` | `/` (empty) | Loans, Repayments |
| `supply_chain` | `/purchases/` | Suppliers, PurchaseOrders, Payments, GoodsReceipts |

**Root URLconf**: `mrms/urls.py` — note `account` and `loan` mount at root with no prefix.

### Critical Pattern: Services Layer

Business logic lives in `services.py` files (`customer/services.py`, `inventory/services.py`, `supply_chain/services.py`), **not** in views or signals. The app deliberately moved from signal-based side effects to explicit service functions called from views.

Key services:
- `customer/services.py`: `record_deposit`, `void_deposit`, `create_sale`, `void_sale`, `create_purchase_agreement`, `cancel_agreement`, `create_cfa_agreement`, `record_cfa_fulfillment`, `void_cfa_fulfillment`
- `inventory/services.py`: `process_transformation`, `void_transformation`
- `supply_chain/services.py`: `process_po`, `process_receipt`, `void_and_correct`, `record_supplier_payment`, `void_supplier_payment`

**Rule**: Do not add new Django signals for business logic. Put it in the services layer instead. The remaining signals in `customer/signals.py` and `inventory/signals.py` are kept only for auto-creation hooks and admin deletion safety nets.

### Cached Balances

`DepositAccount` has cached balance fields (`cached_total_balance`, `cached_allocated_balance`, `cached_available_balance`) that must be refreshed via `_refresh_balances()` (in `customer/services.py`) after any financial mutation. The `populate_cached_balances` management command can rebuild them from scratch. Properties fall back to live calculation if cache is null.

### Audit Logging

Use `core.utils.audit(user, action, obj, detail=None, request=None)` from service functions. Never call from signals.

### Cross-App Model Dependencies

- `customer` models import from `inventory` (Product, TransformationItem, Inventory) and `account` (CustomUser)
- `supply_chain` models import from `inventory` and uses `utils.utils.create_inventory_transaction`
- `inventory` models import from `account` and `utils.utils`
- `loan` models import from `customer` and `account`

### Inventory Transactions

All stock movements create `InventoryTransaction` records via `utils.utils.create_inventory_transaction()`. Transaction types: receipt, sale, transformation, and their reversals.

### HTMX Message Middleware

`middleware.py` at project root contains `HtmxMessageMiddleware` — it serializes Django messages into `HX-Trigger` headers for SweetAlert2 on HTMX responses. Must be last in `MIDDLEWARE` list.

## Models — Key Business Concepts

- **Product**: Boxed (counted) or Coupled (serialized motorcycle with engine/chassis). Creating a boxed motorcycle auto-creates its coupled variant via signal.
- **Transformation**: Converts 1 boxed product → 1 coupled item. Decrement source inventory by 1.
- **DepositAccount → Transaction**: Financial ledger. Deposit, Withdrawal, FulfillmentWithdrawal, Refund types.
- **PurchaseAgreement / CfaAgreement**: Allocate customer deposits to product commitments or CFA (currency) trades.
- **Sale**: Has BoxedSale items and/or CoupledSale items. "From Deposit" sales auto-create fulfillment withdrawals.
- **PurchaseOrder → GoodsReceipt**: Supply chain flow. Receipts update WAC (weighted average cost) on inventory.

## Conventions

- All primary keys are UUID fields with `default=uuid.uuid4`
- Business identifiers use generated prefixes: `CUST-`, `ACCT-`, `DEP-`, `PUR-`, `SALE-`, `B-SALE-`, `C-SALE-`, `CFA-`, `PO-`, `GR-`, `TXN-`, `TRF-`, `ITEM-`
- Models use `created_by`/`updated_by` FKs to `CustomUser` (nullable, SET_NULL)
- `full_clean()` is called in many model `save()` methods — model validation is enforced
- DepositAccount balance validation uses `select_for_update()` to prevent race conditions
- Templates are split: app-level `templates/` dirs for app pages, root `templates/` for shared layouts/partials
- URL names use snake_case (e.g., `record_sale`, `po_detail`, `void_receipt`)
- Views use function-based views (not class-based)
- **`hx-boost="true"` is on `<body>` in `index.html`** — all `<a href>` links and `<form action>` forms are automatically converted to HTMX requests. Do NOT add redundant `hx-get`/`hx-post` or `hx-push-url="true"` on elements that already have `href` or `action` attributes. Only use explicit `hx-get`/`hx-post` when you need to target a different element than the default (`#main_body`) or override the boost behavior.

## Common Pitfalls
- **Modal form pattern**: Every modal uses a single view (GET + POST). GET renders the modal template into `#modal_container`. Valid POST returns `HttpResponse(status=204)` with `HX-Trigger: customerDetailChanged` — the JS `htmx:beforeSwap` listener detects the empty 204 and calls `closeModal()`. Invalid POST or service exception re-renders the modal template as a 200 response; `hx-target="this"` on `#modal-dialog` keeps the swap inside the dialog. Toast notifications come from `messages.success()` / `messages.warning()` / `messages.error()` — `HtmxMessageMiddleware` attaches them to `HX-Trigger` automatically. Never use `_modal_success_response()`, `_customer_detail_context()`, `HX-Retarget`, `HX-Reswap`, or split views. Canonical reference: `modal_deposit` in `customer/views.py` and `customers/modals/deposit_modal.html`.
- **Migration files are gitignored** (`*/migrations/000*.py` in `.gitignore`). Run `python manage.py makemigrations` after model changes.
- **Don't edit signal-connected logic** (like auto-creating coupled products or deposit accounts) without understanding `inventory/signals.py` and `customer/signals.py`.
- **Always use `select_for_update()`** when modifying DepositAccount balances or Inventory quantities in concurrent contexts.
- **Tailwind CSS**: `safelist.html` exists for classes that must be force-included. Edit it when adding dynamic class names that Tailwind's content scan won't catch.
- **`.env` is not committed** — copy values from `requirements.txt`/`settings.py` defaults for dev. `DEBUG=True` is the default.
- **`db.sqlite3` and `db.sqlite3.backup_*` are gitignored** but present locally.
- **Logs and backups directories are gitignored** (`logs/`, `backups/`).
- **The `static/` and `staticfiles/` directories are gitignored** — don't edit files there directly; use source files in `static/css/input.css` and templates.

## Code Consistency Rule — Follow Existing Patterns First

Before implementing any new feature, view, form, UI component, or workflow, you must:

1. **Scan the codebase for an existing implementation of the same category.**
   Examples of categories: modal form operations, HTMX partial renders, tab switching,
   toast notifications, service layer calls, ORM query patterns, URL structures.

2. **If a matching pattern exists, replicate it exactly** — same view structure, same
   response strategy, same template conventions, same URL shape. Do not invent an
   alternative approach just because one exists in your training data.

3. **The canonical reference implementations in this codebase are:**
   - **Modal form operations** (open modal → submit → success toast / inline error):
     See `modal_deposit` view, `customers/modals/deposit_modal.html`, and
     `HtmxMessageMiddleware`. Any modal form anywhere in the codebase must follow
     this exact pattern: one view handling GET + POST, `HttpResponse()` on success,
     `form.add_error(None, ...)` for service exceptions, middleware delivers the toast.
   - Add further reference entries here as the codebase grows.

4. **The only valid reason to deviate from an existing pattern** is if the new
   feature is genuinely different in kind — not just slightly different in shape.
   If you believe a deviation is necessary, state explicitly:
   - What the existing pattern is
   - Why it does not cover this case
   - What you are doing instead and why

5. **Never silently introduce a new pattern** alongside an existing one for the same
   category. If you do this, you create two ways to do the same thing, which causes
   exactly the kind of inconsistency this rule exists to prevent.