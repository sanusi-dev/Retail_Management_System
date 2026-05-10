## Task: Implement Sale Creation System (Ground-Up)

**Context:** You are building the sale creation module from scratch. **Do not reference, reuse, or modify any existing sale-related forms, views, templates, URL patterns, or logic.** Create entirely new implementations for everything described below.

There are **two distinct sale flows**. Both deduct stock from **Boxed Inventory** and **Serialized Inventory** upon successful submission.

---

### Flow 1: Normal Sale

**Purpose:** A standard direct sale to a customer.

#### Entry Point
- A dedicated "Create Normal Sale" page accessible from the main navigation or dashboard.

#### Customer Selection (Searchable + Auto-Create)
- The customer field must be a **searchable dropdown** (e.g., using Select2 or a similar AJAX-powered search).
- **If the searched customer name does not exist in the database:**
  - The user can type the new customer name freely.
  - On form submission, if the customer does not exist, **automatically create a new Customer record** using the entered name before processing the sale.
  - The newly created customer becomes the customer for this sale.
- Display the selected/new customer's current balance prominently on the form (similar to the Purchase Agreement creation page style).

#### Sale Line Items (Formsets)
The form contains two independent formsets on the same page:

**A. Boxed Sale Formset**
- Fields per form: `Product` (dropdown), `Quantity`, `Price` (auto-filled or manual override), etc.
- **Product dropdown filtering:** Only display products that have **available boxed stock > 0**. Products with zero or negative stock must be excluded.
- **Validation:** If the entered `Quantity` exceeds the current available boxed stock for that product, raise a clear form-level validation error on that specific formset row.

**B. Serialized Sale Formset**
- Fields per form: `Product` (dropdown), `Serial Number` (dropdown or input depending on your model), `Price`, etc.
- **Product dropdown filtering:** Only display products that have **available serialized units in stock** (i.e., at least one unassigned serial number). Products with zero available serialized stock must be excluded.
- **Validation:** Prevent selling a serialized unit that is not in stock or already sold.

#### Dynamic Formset Management (HTMX)
- Use **HTMX** to handle adding and removing rows in both formsets **without page reload**.
- **Adopt the exact same rendering and HTMX logic** used in the **Purchase Agreement creation** page for adding/removing inline forms.
- Ensure empty form templates are properly managed and form indices update correctly.

---

### Flow 2: Purchase Agreement Fulfillment Sale

**Purpose:** Converting an existing Purchase Agreement into a fulfilled sale.

#### Entry Point
- On the **Customer Detail Page**, provide a "Fulfill Agreement" button/link.
- Clicking this takes the user to the fulfillment form page, passing the `customer_id` and `agreement_id`.

#### Pre-Populated Fields
- **Customer:** Pre-selected and stored as a **hidden input field**. However, the UI must still **visibly display the customer name and their current balance** (mirror the Purchase Agreement creation page layout).
- **Purchase Agreement:** Pre-selected (hidden or read-only). The user cannot change it on this page.

#### Agreement Line Item Formset
- The formset must render **one form per line item** that exists in the selected Purchase Agreement.
- **Product field:** Each form's product is **locked/pre-filled** to the product from the corresponding agreement line item. The user cannot change the product.
- **Price field:** Pre-populated with the unit price from the agreement line item. The user may or may not be allowed to override this (specify based on your business rules; default to pre-populated).
- **Quantity field:** User enters the quantity they are fulfilling now.
- **Validation:** The quantity entered for each line item **cannot exceed the remaining unfulfilled quantity** for that agreement line item. Display a clear validation error if the user attempts to fulfill more than agreed.

#### Fulfillment Actions on Submit
On successful form submission:
1. Create the **Sale** record.
2. Create the **Fulfillment** record linked to the Purchase Agreement.
3. Handle all related **customer activities** associated with a purchase agreement being fulfilled (e.g., updating agreement status, logging activity, updating customer balance if applicable).
4. Deduct the sold quantities from the appropriate **Boxed** and/or **Serialized** inventory.

---

### Shared Technical Requirements

| Requirement | Details |
|-------------|---------|
| **Inventory Deduction** | Both flows must atomically deduct from Boxed Inventory and Serialized Inventory based on the line items sold. |
| **HTMX Formsets** | All adding/removing of formset rows must use HTMX. Follow the Purchase Agreement creation pattern exactly. |
| **Error Display** | All validation errors (stock limits, agreement quantities, required fields) must render clearly next to their respective fields or formset rows. |
| **Stock Validation** | Normal sale: cannot sell more than available stock. Fulfillment sale: cannot fulfill more than agreement quantity. |
| **Ground-Up Build** | Create new forms, formsets, views, URLs, and templates. Do not inherit from or reference old sale code. |

---

### Deliverables

Provide the complete implementation:

2. **Forms & Formsets** (including custom validation logic for stock and agreement limits)
3. **Views** (one for Normal Sale creation, one for Agreement Fulfillment)
4. **URL Patterns** (new routes for both flows)
5. **Templates** (complete HTML with HTMX attributes for dynamic formsets)
6. **Utility/Service Layer** (if applicable, for inventory deduction and customer creation logic), some service layer alreasdy exist and youre free to use them make modification to them if necessary

---

### Explicit Constraints

- **Do not** use any existing sale forms, views, or templates as a base.
- **Do not** list products with zero stock in any dropdown.
- **Do not** allow fulfillment quantities to exceed the Purchase Agreement line item quantities.
- **Do** create a new customer automatically in the Normal Sale flow if the entered name does not match an existing customer.

---