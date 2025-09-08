# Motorcycle Retail Management System - Project Context

## Project Overview

This is a Django-based web application for managing a motorcycle retail business. The system handles various aspects of the business including inventory management, procurement, sales, customer management, and loan processing.

## Core Technologies

- **Backend**: Python/Django
- **Frontend**: HTMX, Alpine.js, Tailwind CSS (with DaisyUI), jQuery
- **Database**: SQLite (development), designed for PostgreSQL (production)
- **Build Tools**: esbuild for JavaScript, PostCSS for CSS

## Project Structure

```
Motorcycle_Retail_Management_System/
├── account/           # User authentication and custom user model
├── core/              # Main dashboard and core functionality
├── customer/          # Customer management and sales processing
├── inventory/         # Product and inventory management
├── loan/              # Loan processing and repayment tracking
├── mrms/              # Main Django project settings and configuration
├── scripts/           # Data population and utility scripts
├── services/          # Business logic services
├── supply_chain/      # Procurement, suppliers, purchase orders
├── templates/         # HTML templates with partials
├── theme/             # Tailwind CSS configuration and static assets
└── utils/             # Utility functions and helpers
```

## Business Domain

The application manages a complete motorcycle retail business with these key modules:

1. **Account Management**:
   - Custom user model extending Django's AbstractUser
   - Authentication and authorization

2. **Inventory Management**:
   - Product catalog with brands, models, and variants
   - Serialized inventory tracking (engine/chassis numbers)
   - General inventory quantities
   - Inventory transformations (boxed to coupled)

3. **Supply Chain**:
   - Supplier management
   - Purchase orders
   - Goods receipt processing
   - Payment tracking

4. **Customer Management**:
   - Customer database
   - Sales transactions
   - Sale items with serialized product tracking

5. **Loan Processing**:
   - Sales financing
   - Loan repayments
   - Payment tracking

## Frontend Architecture

- **HTMX**: Used for dynamic page updates without full page refreshes
- **Alpine.js**: For interactive UI components
- **Tailwind CSS**: Utility-first CSS framework with DaisyUI components
- **Responsive Design**: Mobile-friendly layout with collapsible sidebar

## Key Commands

### Development

1. **Run Django Development Server**:
   ```bash
   python manage.py runserver
   ```

2. **Run Tailwind CSS Development Build**:
   ```bash
   python manage.py tailwind start
   ```
   Or alternatively:
   ```bash
   cd theme/static_src && npm run start
   ```

3. **Populate Initial Data**:
   ```bash
   python manage.py runscript populate_product_model
   python manage.py runscript populate_brand_model
   python manage.py runscript populate_supplier_model
   ```

### Production Build

1. **Build Frontend Assets**:
   ```bash
   cd theme/static_src && npm run build
   ```

2. **Collect Static Files**:
   ```bash
   python manage.py collectstatic
   ```

## Data Models

### Core Entities

- **Brand**: Motorcycle brand/manufacturer
- **Product**: Motorcycle models with variants (boxed/coupled)
- **Inventory**: General inventory quantities
- **SerializedInventory**: Individual unit tracking with engine/chassis numbers
- **Supplier**: Vendor information
- **PurchaseOrder**: Procurement orders
- **Customer**: Client information
- **Sale**: Sales transactions
- **Loan**: Financing arrangements

## Development Conventions

### Backend

- Follow Django best practices
- Use class-based views where appropriate
- Implement proper validation in models
- Use UUIDs as primary keys for most models
- Implement proper foreign key relationships with `on_delete` behaviors
- Use Django's built-in authentication system

### Frontend

- Use HTMX for dynamic interactions
- Implement Alpine.js for complex UI state
- Follow Tailwind CSS utility class patterns
- Maintain responsive design principles
- Use template partials for reusable components

### Data Management

- Use Django scripts for data population
- Implement proper data constraints at the model level
- Use proper migration management
- Follow consistent naming conventions for URLs and views

## Deployment Considerations

- The application is configured for Heroku deployment
- Uses Procfile-based process management
- Static files are collected to `staticfiles` directory
- Environment variables are managed through `.env` file
- Tailwind CSS is compiled from the `theme` app

## Key URLs

- `/` - Dashboard
- `/products/` - Product management
- `/purchases/` - Procurement management
- `/suppliers/` - Supplier management
- `/receipts/` - Goods receipt management
- `/payments/` - Payment processing

## Custom User Model

The application uses a custom user model (`account.CustomUser`) that extends Django's AbstractUser. This is configured in `settings.py` with `AUTH_USER_MODEL = "account.CustomUser"`.

## Template Structure

The application uses a base template (`templates/index.html`) with:
- Header and sidebar navigation
- Main content area
- Reusable partials for UI components
- HTMX integration for dynamic updates