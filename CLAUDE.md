# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django-based Retail Management System (RMS) for a Nigerian motorcycle/engine distributor. The business operates a deposit-funded purchase agreement system with serialised inventory and CFA forex allocation. The system manages the complete business cycle: procurement, assembly, sales, and complex customer ledger management.

**Tech Stack:**
- Backend: Django 5.2.x with Python 3.x
- Frontend: Django Templates + HTMX + Alpine.js + Tailwind CSS
- Database: SQLite (WAL mode) — PostgreSQL planned for future
- WSGI: waitress (desktop packaging)
- Deployment: Windows desktop application (offline-first)

## Common Commands

```bash
# Run the development server
python manage.py runserver

# Run a single test
python manage.py test <app_name>.<test_module>.<TestClass>.<test_method>

# Create migrations
python manage.py makemigrations <app_name>

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic
```

## Project Structure

The codebase is organized into modular Django apps:

| App | Purpose |
|-----|---------|
| `account` | CustomUser model, authentication |
| `core` | Dashboard, shared context processors |
| `inventory` | Products, brands, stock ledger, transformations |
| `supply_chain` | Suppliers, purchase orders, goods receipts, payments |
| `customer` | Customers, deposits, purchase agreements, CFA agreements, sales |
| `loan` | Loan module (stub) |
| `theme` | Static assets |

URLs are defined in each app's `urls.py` and included in `mrms/urls.py`.

## Key Architecture Decisions

### Service Layer Pattern (Target)
Business logic currently lives in signals and model methods. The refactoring target is:
```
views.py → services.py → models.py
```

Services already exist in `inventory/services.py`, `supply_chain/services.py`, and `customer/services.py` (empty). Business logic should move into explicit service functions — signals should become thin wrappers or be removed.

### Dependency Cleanup (In Progress)
Per the reconstruction document, these packages should be removed:
- `django-tailwind` → use Tailwind CSS standalone CLI
- `django-render-block` → use `django-template-partials`
- `django-easy-audit` → replace with custom AuditLog model
- `django-browser-reload` → dev-only
- `django-environ` → use `python-decouple`
- `django-extensions` → not meaningfully used

### Financial Transaction Pattern
Balance read-modify-write operations must use explicit transactions. Current SQLite handling is inconsistent; prefer explicit `transaction.atomic()` blocks.

### Audit Trail
Every model should track `created_by` / `updated_by` foreign keys. Audit logging should use explicit service calls, not signals.

## IDE Configuration

VS Code is configured with:
- Python formatter: black (`ms-python.black-formatter`)
- HTML/Django template formatter: djlint (`monosans.djlint`)
- Font: Ubuntu Mono
- Theme: VS Code Dark

See `.vscode/settings.json` for full configuration.

## Important Files

- `mrms/settings.py` — Django settings
- `mrms/urls.py` — Root URL configuration
- `reconstruction_document.md` — Detailed refactoring roadmap and architectural decisions
- `middleware.py` — Custom middleware (check if still needed)

## Testing

Tests exist in `core/tests.py`, `supply_chain/tests.py`, and `inventory/tests.py`. No pytest configured — uses Django's built-in test runner.