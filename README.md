# Retail Management System

A Django web application for managing motorcycle dealership operations —
inventory, customer deposits, sales, supply chain, and financial tracking.
Built for the Nigerian market with support for boxed and serialized (coupled)
motorcycle products, deposit-based purchase agreements, and CFA currency trading.

## Architecture

The project (`mrms`) is organised into five Django apps, each with a clear
domain boundary. All business logic lives in dedicated `services.py` modules
and is explicitly invoked from views — never from Django signals.

| App | URL Prefix | Responsibility |
|---|---|---|
| `account` | `/` | Authentication, custom user model |
| `core` | `/` (dashboard) | Dashboard, audit log, shared utilities |
| `customer` | `/customer/` | Customers, deposit accounts, transactions, purchase & CFA agreements, sales |
| `inventory` | `/inventory/` | Products, brands, stock levels, transformations (boxed → coupled) |
| `supply_chain` | `/purchases/` | Suppliers, purchase orders, payments, goods receipts |

## Key Features

### Customer & Financial Management
- Customer profiles with auto-created deposit accounts
- Deposit ledger with full transaction history (deposits, withdrawals, refunds)
- Purchase agreements — allocate customer deposits toward specific products before delivery
- CFA (currency) trading — allocate funds to XOF exchange with configurable rates
- Cached balance system with `populate_cached_balances` / `verify_cached_balances` management commands

### Sales
- Cash, bank transfer, and "from deposit" payment methods
- Boxed sales (counted inventory items) and coupled sales (serialized, post-assembly units)
- FIFO cost tracking — cost of goods sold is calculated from oldest inventory layers first
- Full void workflow — reversing a sale restores inventory, FIFO layers, and refunds deposits

### Inventory & Transformations
- Product catalogue with brands and model variants (boxed / coupled)
- Automatic coupled variant creation when a boxed motorcycle is registered
- Real-time stock levels via `InventoryTransaction` audit ledger
- Weighted average cost (WAC) recalculation on every goods receipt
- Transformation workflow — convert boxed units to coupled units with engine/chassis numbers

### Supply Chain
- Purchase order creation with multi-line items
- Goods receipt processing with automatic WAC adjustment and FIFO cost layer creation
- Supplier payment tracking with payment status lifecycle (pending → partial → fulfilled)
- Receipt void and correction with automatic stock reversal and WAC recalculation

### Audit & Security
- Immutable audit log of all destructive actions (voids, cancellations, adjustments)
- Login-required middleware on all routes
- CSRF, HSTS, and secure cookie configuration for production
- Function-based views with explicit permission checks

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0, Python 3.12 |
| Database | SQLite (default); PostgreSQL via `DATABASE_URL` |
| Frontend | Tailwind CSS, HTMX, Alpine.js |
| Static Files | Whitenoise with compressed manifest storage |
| Notifications | SweetAlert2 toasts via custom `HtmxMessageMiddleware` |

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd Retail_Management_System

# 2. Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt
npm install

# 4. Set up environment
cp .env.example .env
# Edit .env with your SECRET_KEY

# 5. Build and migrate
npm run build:css
python manage.py migrate
python manage.py createsuperuser

# 6. Seed demo data (optional)
python manage.py seed_demo_data

# 7. Run the development server
python manage.py runserver            # terminal 1
npm run watch:css                     # terminal 2 (auto-rebuilds CSS)
```

Access the app at `http://127.0.0.1:8000/`.

### Demo Credentials

| User | Password | Role |
|---|---|---|
| `admin` | `demo1234` | Superuser (full access) |
| `staff` | `demo1234` | Staff (limited access) |

## Deployment

The project is configured for Render.com deployment via `render.yaml`.
The build sequence runs `npm install`, Tailwind CSS build, `pip install`,
`collectstatic`, `migrate`, and `seed_demo_data` automatically.

```bash
# Run the build script locally to verify
./build.sh
```

### Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key | Required |
| `DJANGO_ENVIRONMENT` | Sets dev or production mode | `dev` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `127.0.0.1,localhost` |
| `DATABASE_URL` | Database connection string | SQLite |
| `CSRF_TRUSTED_ORIGINS` | CSRF trusted origins (production) | — |
| `DEBUG` | Debug mode (dev only) | `True` |

## Development

### Running Tests

```bash
python manage.py test                          # all apps
python manage.py test customer                 # single app
python manage.py test customer.tests.test_financial_logic  # single module
```

Tests use Django's built-in test runner with Faker for data generation.

### Management Commands

```bash
python manage.py seed_demo_data               # seed realistic demo data
python manage.py populate_cached_balances     # rebuild DepositAccount cache
python manage.py verify_cached_balances       # audit cache against live calculation
```

### Code Quality

```bash
djlint --lint inventory/templates/   # template linting
```

## Design Decisions

**Services layer over signals.** Business logic (deposits, sales,
transformations, purchase orders) is explicitly invoked from views through
`services.py` modules. This keeps side effects traceable and avoids the
implicit coupling that signal-driven architectures create.

**Cached financial balances.** `DepositAccount` holds denormalised balance
fields refreshed after every financial mutation. Properties fall back to
live calculation if the cache is null, ensuring correctness even after
schema changes.

**Immutable audit trail.** All destructive or irreversible actions write to
`core.AuditLog`. Audit entries are append-only with no delete pathway.

**Function-based views.** All views are plain functions. HTMX `hx-boost` on
`<body>` provides SPA-like navigation without a frontend framework. The
custom `HtmxMessageMiddleware` bridges Django's messages framework to
SweetAlert2 toast notifications on HTMX responses.

## License

Proprietary. All rights reserved.
