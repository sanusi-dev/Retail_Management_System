# Retail Management System

A Django-based application for managing retail motorcycle dealership operations. Designed
for businesses that sell boxed and serialized motorcycles, manage customer deposits, handle
purchase agreements, and track inventory through the supply chain.

## Features

### Customer Management
- Customer profiles with linked deposit accounts
- Deposit ledger with full transaction history (deposits, withdrawals, refunds)
- Purchase agreements &mdash; allocate customer deposits toward specific products
- CFA (currency) trading with configurable exchange rates
- Cached balance system for performant financial summaries

### Sales
- Record sales for boxed (countable) and coupled (serialized) motorcycle products
- "From Deposit" fulfilment that auto-deducts allocated customer balances
- Full void/correction workflow with inventory restocking
- Asset serial number management (engine / chassis numbers)

### Inventory
- Product catalogue with brands, categories, and product types
- Real-time stock levels via `InventoryTransaction` ledger
- Weighted average cost (WAC) tracking on goods receipt
- Boxed &rarr; Coupled transformation (assembly) workflow
- Void and correction support for all movements

### Supply Chain
- Purchase order creation with line-item management
- Goods receipt processing with automatic WAC adjustment
- Supplier payment tracking against purchase orders
- Receipt void with automatic stock reversal

### Loan Management
- Loan origination with configurable terms
- Repayment tracking and schedules
- Integration with customer deposit accounts

### Audit & Administration
- Immutable audit log of all destructive/irreversible actions
- Custom Django admin with enhanced views and filters
- Management commands for cached-balance maintenance and verification

## Tech Stack

| Layer         | Technology                                      |
|---------------|-------------------------------------------------|
| **Backend**   | Django 6.0, Python 3.x                         |
| **Database**  | SQLite (default); swappable to PostgreSQL       |
| **Frontend**  | Tailwind CSS, HTMX, Alpine.js                  |
| **Assets**    | npm / Tailwind CLI                             |
| **Static**    | Whitenoise                                     |
| **Icons**     | Inline SVG (no icon library dependency)        |
| **Notifs**    | SweetAlert2 toasts via `HtmxMessageMiddleware` |

## Architecture

The project (`mrms`) is organised into six Django apps with clear domain boundaries.

| App            | URL Prefix      | Responsibility                                |
|----------------|-----------------|-----------------------------------------------|
| `account`      | `/`             | Authentication, custom user model             |
| `core`         | `/` (dashboard) | Dashboard, audit log, shared utilities        |
| `customer`     | `/customer/`    | Customers, deposits, transactions, agreements |
| `inventory`    | `/inventory/`   | Products, brands, inventory, transformations  |
| `loan`         | `/`             | Loans and repayments                          |
| `supply_chain` | `/purchases/`   | Suppliers, purchase orders, goods receipts    |

All business logic lives in dedicated `services.py` modules, called from views.
Django signals are kept to a minimum&mdash;used only for auto-creation hooks and
admin deletion safety nets.

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd Retail_Management_System

# 2. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt
npm install

# 4. Environment configuration
#    Create a .env file with at minimum:
#      SECRET_KEY=<your-secret-key>
#      DEBUG=True
cp .env.example .env   # if an example file exists

# 5. Database setup
python manage.py migrate
python manage.py createsuperuser

# 6. Build frontend assets (tailwind/css)
npm run build:css

# 7. Run the development server
python manage.py runserver            # terminal 1
npm run watch:css                     # terminal 2 (auto-rebuilds CSS)
```

## Development

### Running Tests

```bash
python manage.py test                     # all apps
python manage.py test customer            # single app
python manage.py test customer.tests.test_financial_logic  # single module
```

Tests use Django's built-in test runner. Test factories use [Faker](https://faker.readthedocs.io/).

### Linting & Type Checking

```bash
djlint --lint inventory/templates/       # template linting
mypy .                                   # type checking (django-stubs)
```

### Key Management Commands

```bash
python manage.py populate_cached_balances  # rebuild DepositAccount cache
python manage.py verify_cached_balances    # audit cache against live calculation
python manage.py collectstatic             # production static collection
```

## Design Decisions

**Services layer over signals.** Business logic (deposits, sales, transformations,
purchase orders) is explicitly invoked from views through `services.py` modules.
This keeps side effects traceable and avoids the implicit coupling that
signal-driven architectures create.

**Cached financial balances.** `DepositAccount` holds denormalised balance fields
that are refreshed after every financial mutation. Properties fall back to live
calculation if the cache is null, ensuring correctness even after schema changes.

**Immutable audit trail.** All destructive or irreversible actions (voids,
cancellations, manual adjustments) write to `core.AuditLog`. Audit entries are
append-only with no delete pathway.

**Function-based views.** All views are plain functions, not class-based.
HTMX `hx-boost` on `<body>` provides SPA-like navigation without a frontend
framework. HtmxMessageMiddleware bridges Django's messages framework to
SweetAlert2 toast notifications on HTMX responses.

## License

Proprietary. All rights reserved.
