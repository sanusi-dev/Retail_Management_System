# FIFO Implementation — Complete Reference

## 1. NEW MODELS INTRODUCED

### 1.1 `InventoryCostLayer` — `inventory/models.py:243-280`

The core FIFO data structure. Each goods receipt creates one cost layer for each
product it delivers. Layers are consumed oldest-first on sale and
transformation.

| Field | Type | Purpose |
|---|---|---|
| `cost_layer_id` | `UUIDField` pk | Standard UUID primary key |
| `product` | `FK(Product, CASCADE, related_name="cost_layers")` | Which product this batch belongs to. CASCADE means deleting a product also removes its layers |
| `quantity` | `PositiveIntegerField` | The original number of units received in this batch. Set once at creation and never modified, serving as audit trail |
| `remaining_quantity` | `PositiveIntegerField` | How many units from this batch are still in stock. Decremented by sales and transformations. Incremented on reversals. This is the field that drives FIFO depletion logic |
| `unit_cost` | `DecimalField(10,2)` | Per-unit cost at receipt time (PO unit price plus allocated delivery cost). Set once at creation, never modified |
| `goods_receipt_item` | `FK("supply_chain.GoodsReceiptItem", SET_NULL, null=True, related_name="cost_layers")` | Links the cost layer back to the receipt item that created it. Used by `void_and_correct` to locate and void the layer when a receipt is voided. SET_NULL so the layer survives if the receipt item is deleted |
| `is_voided` | `BooleanField(default=False)` | Set to `True` when the receipt that created this layer is voided. Voided layers are excluded from depletion queries so sales and transformations skip them |
| `voided_at` | `DateTimeField(null=True, blank=True)` | Timestamp of when the receipt was voided. `None` for active layers |
| `created_at` | `DateTimeField(auto_now_add=True)` | The FIFO ordering key — layers are consumed in ascending `created_at` order |

**Meta:** `ordering = ["created_at"]` (oldest first, matching FIFO semantics).

**Indexes:**
- `(product, created_at)` — primary query pattern: all layers for a product in FIFO order
- `(goods_receipt_item)` — used by `void_and_correct` to find the layer linked to a specific receipt item

### 1.2 `BoxedSaleLayerConsumption` — `customer/models.py:1129-1154`

A junction model recording exactly which `InventoryCostLayer` rows were depleted
by each `BoxedSale`. When a sale is voided, these records are used to restore
units to their original layers, preserving FIFO order.

| Field | Type | Purpose |
|---|---|---|
| `id` | implicit auto | — |
| `boxed_sale` | `FK("BoxedSale", CASCADE, related_name="layer_consumptions")` | Which sale consumed these units. CASCADE means deleting a sale cleans up its consumption records |
| `cost_layer` | `FK(InventoryCostLayer, PROTECT, related_name="sale_consumptions")` | Which FIFO layer was consumed from. PROTECT prevents accidental deletion of a layer with sale history |
| `quantity_consumed` | `PositiveIntegerField` | Number of units from this specific layer consumed by this sale |
| `unit_cost` | `DecimalField(10,2)` | Snapshotted unit cost at time of consumption. Stored denormalized so reversal cost can be calculated without joining back to the layer |
| `created_at` | `DateTimeField(auto_now_add=True)` | Audit timestamp |

**Indexes:**
- `(boxed_sale)` — fast lookup of all layers consumed by a sale (used in `void_sale`)
- `(cost_layer)` — reverse lookup: which sales consumed from a given layer

A single BoxedSale that consumed from multiple layers produces one
BoxedSaleLayerConsumption row per layer.

---

## 2. EXISTING MODELS MODIFIED

### 2.1 `BoxedSale` — `customer/models.py:1157-1306`

**Field added:** `cost_basis` (line 1171-1174)

```python
cost_basis = models.DecimalField(
    max_digits=15, decimal_places=2, null=True, blank=True,
    help_text="Total FIFO cost of units sold at sale time",
)
```

| Aspect | Detail |
|---|---|
| What it stores | The **total** FIFO cost across all layers consumed for this sale. Example: a sale of 10 units pulling 6 from a layer at cost 200 and 4 from a layer at cost 260 stores `(6×200)+(4×260) = 2240.00` |
| When it gets written | In `create_sale()` at `customer/services.py:365` after `_deplete_fifo_layers()` returns |
| What reads it | `BoxedSale.profit` (line 1301-1306) — subtracts it from total revenue. `product_detail` view (`inventory/views.py:414-415`) — same calculation. `void_sale()` (`customer/services.py:487`) — legacy fallback for sales without `layer_consumptions`. `customer/signals.py:64` — admin deletion handler |
| Why nullable | Sales created before FIFO have no cost layers to calculate from. When `None`, profit falls back to WAC |

**Property modified:** `BoxedSale.profit` (line 1300-1306)

Two-path logic:
- If `cost_basis is not None`: `profit = (price × quantity) - cost_basis`
- If `cost_basis is None`: `profit = (price - WAC) × quantity` (fallback for pre-FIFO sales)

### 2.2 `TransformationItem` — `inventory/models.py:373-480`

**Field added:** `consumed_layer` (lines 413-420)

```python
consumed_layer = models.ForeignKey(
    InventoryCostLayer,
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name="transformation_consumptions",
    help_text="The FIFO cost layer consumed during this transformation",
)
```

| Aspect | Detail |
|---|---|
| What it stores | A pointer to the single `InventoryCostLayer` depleted to produce this coupled unit (always exactly 1 unit per transformation item) |
| When it gets written | In `process_transformation()` at `inventory/services.py:179` |
| What reads it | `create_reversal()` (line 469-471) — increments `remaining_quantity` on the original layer during void. `void_transformation()` (line 227) — checks for NULL to trigger legacy fallback |
| Why nullable + SET_NULL | Legacy `TransformationItem` rows created before FIFO have no consumed layer. On void, these fall back to creating a new layer. If the layer is deleted, the FK becomes NULL and the fallback applies |

**Fields modified:** `source_product` and `target_product` (lines 387-400)

Both FK fields now carry `limit_choices_to` constraints:

| Field | Constraint |
|---|---|
| `source_product` | `{"type_variant": Product.TypeVariant.BOXED}` — only boxed products can be transformation sources |
| `target_product` | `{"type_variant": Product.TypeVariant.COUPLED}` — only coupled products can be transformation targets |

These are enforced at the ORM level in forms and the Django admin. A `clean()` method provides a second validation layer for programmatic saves.

**Method added:** `clean()` (lines 444-452)

Validates that `source_product.type_variant == BOXED` and
`target_product.type_variant == COUPLED`, raising `ValidationError` with
field-specific error messages on violation. Both checks are null-safe.

**Method modified:** `save()` (lines 476-479)

Calls `self.full_clean()` before `super().save()`, ensuring the `clean()`
validation runs on every save — form-based and programmatic alike.

**Method modified:** `create_reversal()` (lines 454-474)

Two FIFO-specific behaviors:
1. **Cost source** (line 459): Uses `self.unit_cost_at_transformation - self.allocated_service_fee` as the reversal `cost_impact`, extracting the original FIFO source cost (without service fee) that was snapshotted at transformation time.
2. **Layer restoration** (lines 469-471): If `self.consumed_layer` is set, increments `remaining_quantity += 1` on the original layer directly, preserving its FIFO position.

### 2.3 `customer/models.py` import change (line 23)

Extended the import from `inventory.models` to include `InventoryCostLayer`,
required by `BoxedSaleLayerConsumption.cost_layer`.

---

## 3. NEW METHODS AND FUNCTIONS

### 3.1 `_deplete_fifo_layers(product, quantity)` — `inventory/services.py:15-93`

**Arguments:** `product` (Product instance), `quantity` (int)

**Returns:** `(total_cost, consumption_entries)` tuple where:
- `total_cost` is `Decimal` — the sum of `quantity × unit_cost` across all layers consumed
- `consumption_entries` is `list[dict]` — each dict has keys `"layer"` (InventoryCostLayer instance), `"quantity"` (int), `"unit_cost"` (Decimal)

**Step-by-step logic:**

1. **Query layers** (lines 29-37): Fetch `InventoryCostLayer` rows for the given product where `remaining_quantity > 0` and `is_voided = False`, ordered by `created_at` ASC, locked with `select_for_update()`. The `is_voided=False` filter ensures that layers from voided receipts are invisible to sales and transformations.

2. **Fallback check** (lines 38-67): Sum all `remaining_quantity` values. If the total is less than `quantity`, the function creates a synthetic `InventoryCostLayer` for the gap using the current `Inventory.weighted_average_cost`. It then re-fetches layers (including the new synthetic one) with `select_for_update()`. If `Inventory.quantity < quantity`, raises `BusinessRuleViolation`.

3. **Depletion loop** (lines 69-85): Iterates layers in FIFO order. For each layer, takes `min(layer.remaining_quantity, remaining_to_deplete)`, decrements `layer.remaining_quantity`, saves it, accumulates cost into `total_cost`, and appends a consumption entry dict.

4. **Final guard** (lines 87-91): If `remaining_to_deplete > 0` after the loop, raises `BusinessRuleViolation`.

5. **Return** (line 93): `(total_cost, consumption_entries)`.

**Concurrency:** Uses `select_for_update()` on the queried layers within a
transaction. Callers also hold a `select_for_update()` lock on the `Inventory`
row.

**Callers:**
- `create_sale()` in `customer/services.py:364` — for boxed sales
- `process_transformation()` in `inventory/services.py:175` — for transformations (always `quantity=1`)

### 3.2 `_restore_fifo_layer(product, quantity, unit_cost)` — `inventory/services.py:96-108`

**Arguments:** `product` (Product), `quantity` (int), `unit_cost` (Decimal)

**Returns:** None

**Purpose:** Creates a brand new `InventoryCostLayer` with the given parameters
and `created_at=now()`, placing it at the back of the FIFO queue. Used as a
fallback when reversal cannot restore to an original layer (legacy records
without `BoxedSaleLayerConsumption` or `consumed_layer`).

**Callers:**
- `void_sale()` in `customer/services.py:492` — legacy sale backward-compatibility path
- `void_transformation()` in `inventory/services.py:229` — legacy transformation backward-compatibility path
- `customer/signals.py:68` — admin deletion backward-compatibility path

### 3.3 `TransformationItem.clean()` — `inventory/models.py:444-452`

Validates type-variant constraints on source and target products. Called
automatically from `save()` via `full_clean()`. Raises `ValidationError` with
field-keyed dictionaries so errors appear next to the correct form field.

---

## 4. MODIFIED METHODS AND FUNCTIONS

### 4.1 `process_receipt(form, formset, user)` — `supply_chain/services.py:40-119`

For each receipt item, after the WAC recalculation and inventory update, the
function creates an `InventoryCostLayer` (lines 94-101):

```python
InventoryCostLayer.objects.create(
    product=item.product,
    quantity=qty,
    remaining_quantity=qty,
    unit_cost=cost,
    goods_receipt_item=item,
)
```

Where `qty = item.received_quantity` and `cost = item.unit_cost_at_receipt` (PO
unit price plus allocated delivery cost). This is the sole entry point for new
FIFO layers — every goods receipt produces one layer per product line.

### 4.2 `void_and_correct(receipt_id, user, request=None)` — `supply_chain/services.py:132-213`

For each receipt item, after creating the reversal receipt item and its
InventoryTransaction via `item.create_reversal(user)`, the function voids the
corresponding FIFO cost layer (lines 152-170):

1. **Lookup** (lines 153-155): Since one receipt item creates exactly one
   `InventoryCostLayer` (see `process_receipt`), queries with
   `goods_receipt_item=item` and `.first()` directly — no iteration needed.

2. **Sold-units check** (lines 160-163): If `cost_layer.remaining_quantity <
   item.received_quantity`, some units were already sold from this batch. The
   function computes how many were sold and raises `BusinessRuleViolation`.

3. **Mark voided** (lines 164-168): Instead of depleting `remaining_quantity`
   (which would be indistinguishable from a sale), the function sets
   `is_voided = True`, zeroes `remaining_quantity`, and records `voided_at =
   timezone.now()`. This makes the layer's voided state explicit and
   immediately visible.

The `is_voided` flag means `_deplete_fifo_layers` automatically skips this
layer in all future queries, without needing any additional checks. The layer
row persists for audit purposes (`quantity` and `unit_cost` are preserved).

### 4.3 `process_transformation(form, formset, request)` — `inventory/services.py:125-195`

For each transformation item (lines 174-182):

1. Calls `_deplete_fifo_layers(item.source_product, 1)` to consume one unit from the boxed product's oldest layer.
2. Sets `item.unit_cost_at_transformation = fifo_cost + service_fee_per_item`.
3. Sets `item.consumed_layer = consumptions[0]["layer"]` — stores a pointer to the specific layer consumed.
4. Saves the item (triggering `full_clean()` validation).
5. Creates an `InventoryTransaction` with `cost_impact = fifo_cost`.

Inventory quantity is decremented (line 172) before `_deplete_fifo_layers` is
called, so the fallback path in that function sees the accurate quantity.

### 4.4 `void_transformation(transformation_id, user, request=None)` — `inventory/services.py:207-243`

For each transformation item (lines 222-229):

1. Calls `item.create_reversal()` which handles inventory restoration and reversal transaction creation. If `item.consumed_layer` is set, `create_reversal()` also increments `remaining_quantity` on the original layer.
2. If `item.consumed_layer is None` (legacy item), calls `_restore_fifo_layer()` to create a new layer at the back of the FIFO queue as a fallback.

### 4.5 `create_sale(sale, boxed_items, coupled_items, user, request=None)` — `customer/services.py:332-448`

For each boxed sale item (lines 358-383):

1. Decrements `Inventory.quantity` (line 360).
2. Calls `_deplete_fifo_layers(item.product, item.quantity)` which returns `(fifo_cost, consumptions)` (line 364).
3. Sets `item.cost_basis = fifo_cost` and saves (lines 365-366).
4. Iterates `consumptions` and creates one `BoxedSaleLayerConsumption` row per consumed layer, recording the layer reference, quantity, and unit cost (lines 369-375).
5. Creates an `InventoryTransaction` with `cost_impact = fifo_cost` (lines 377-383).

The coupled sale processing (lines 406-442) is unchanged — it uses
`TransformationItem.unit_cost_at_transformation` which was already snapshotted
at transformation time using FIFO.

### 4.6 `void_sale(sale_id, void_reason, user, request=None)` — `customer/services.py:451-553`

For each boxed sale in the voided sale (lines 472-503), the cost reversal uses
three priority tiers:

1. **`layer_consumptions` exist** (lines 480-486): Iterates `boxed_sale.layer_consumptions.all()`. For each record, increments `remaining_quantity` on the original `InventoryCostLayer` directly. Accumulates `reversal_cost` from `quantity_consumed × unit_cost`. This preserves the exact layer identities and FIFO positions.

2. **Only `cost_basis` exists** (lines 487-492): A backward-compatibility path for sales created with a cost basis but without granular `BoxedSaleLayerConsumption` records. Calls `_restore_fifo_layer()` to create a new averaged layer at the back of the FIFO queue. `reversal_cost = boxed_sale.cost_basis`.

3. **Neither exists** (lines 493-494): Pre-FIFO sales. Uses `inventory.weighted_average_cost × quantity` for the reversal cost, with no layer restoration.

The reversal `InventoryTransaction` uses the computed `reversal_cost`.

### 4.7 `product_detail` view — `inventory/views.py:411-418`

The boxed profit aggregation loop uses `cost_basis` when available, falling
back to WAC for pre-FIFO sales:

```python
if bs.cost_basis is not None:
    boxed_profit += (bs.price * bs.quantity) - bs.cost_basis
else:
    wac = bs.product.inventory.weighted_average_cost or Decimal("0.00")
    boxed_profit += (bs.price - wac) * bs.quantity
```

### 4.8 `customer/signals.py:49-78` — `return_inventory_on_sale_deletion`

The `post_delete` handler on `BoxedSale` uses the same three-tier strategy as
`void_sale` to restore inventory and FIFO layers when a sale is deleted via the
Django admin.

---

## 5. FIFO COST FLOW

### 5.1 Boxed Sale — Receipt Through Profit

```
GOODS RECEIPT
│
├── supply_chain/services.py:process_receipt()
│   │
│   ├── [line 71] unit_cost_at_receipt = unit_price_at_order + allocated_delivery
│   ├── [line 88] Recalculates Inventory.weighted_average_cost (for valuation)
│   ├── [line 95] Creates InventoryCostLayer:
│   │       quantity = received_quantity
│   │       remaining_quantity = received_quantity
│   │       unit_cost = unit_cost_at_receipt
│   │       goods_receipt_item = receipt_item
│   └── [line 105] Creates InventoryTransaction (type=receipt, cost_impact=qty×cost)
│
│   [Additional receipts create additional layers with distinct unit_cost,
│    created_at, and remaining_quantity]
│
▼
BOXED SALE
│
├── customer/services.py:create_sale()
│   │
│   ├── [line 360] inventory.quantity -= item.quantity
│   ├── [line 364] fifo_cost, consumptions = _deplete_fifo_layers(product, qty)
│   │       → inventory/services.py:73-84: iterates layers oldest-first,
│   │         depletes remaining_quantity, returns total cost + consumption list
│   ├── [line 365] item.cost_basis = fifo_cost
│   ├── [lines 369-375] Creates BoxedSaleLayerConsumption records per layer
│   └── [line 377] Creates InventoryTransaction (type=sale, cost_impact=fifo_cost)
│
▼
PROFIT
│
├── customer/models.py:BoxedSale.profit [line 1300]
│   └── (price × quantity) − cost_basis
│
│   Example: 10 units at price 320, consuming 6 @ 200 and 4 @ 260
│   cost_basis = (6×200) + (4×260) = 2240
│   profit = 3200 − 2240 = 960
```

### 5.2 Coupled Sale — Receipt Through Profit

```
GOODS RECEIPT → InventoryCostLayer created (same as boxed flow above)

TRANSFORMATION
│
├── inventory/services.py:process_transformation()
│   │
│   ├── [line 172] inventory.quantity -= 1 (boxed product)
│   ├── [line 175] fifo_cost, consumptions = _deplete_fifo_layers(source_product, 1)
│   ├── [line 176] item.unit_cost_at_transformation = fifo_cost + service_fee
│   ├── [line 179] item.consumed_layer = consumptions[0]["layer"]
│   ├── [line 182] item.save() → triggers full_clean()
│   └── [line 185] InventoryTransaction (type=transformation, cost_impact=fifo_cost)
│
▼
COUPLED SALE
│
├── customer/services.py:create_sale() — coupled items [lines 406-442]
│   └── Marks TransformationItem as SOLD. No cost calculation needed —
│       unit_cost_at_transformation was already snapshotted.
│
▼
PROFIT
│
├── customer/models.py:CoupledSale.profit [line 1122]
│   └── price − transformation_item.unit_cost_at_transformation
│
│   Example: service_fee=5, source FIFO cost=200 → unit_cost=205
│   profit = 320 − 205 = 115
```

---

## 6. REVERSAL FLOWS

### 6.1 Boxed Sale Reversal

```
customer/services.py:void_sale()
│
├── [line 477] inventory.quantity += boxed_sale.quantity
│
├── [line 480] consumptions = boxed_sale.layer_consumptions.all()
│
├── PATH A: Layer consumptions exist (normal FIFO path)
│   ├── For each BoxedSaleLayerConsumption c:
│   │   ├── c.cost_layer.remaining_quantity += c.quantity_consumed
│   │   ├── c.cost_layer.save(update_fields=["remaining_quantity"])
│   │   └── reversal_cost += c.quantity_consumed * c.unit_cost
│   │
│   │   The original layers regain their units. created_at is unchanged,
│   │   so FIFO order is preserved. No new layers are created.
│
├── PATH B: Only cost_basis exists (backward compatibility)
│   │   _restore_fifo_layer(product, qty, cost_basis/qty)
│   │   reversal_cost = cost_basis
│   │
│   │   Creates a single averaged layer at the back of the FIFO queue.
│
└── PATH C: Neither exists (pre-FIFO)
    └── reversal_cost = inventory.wac * qty  (no layer restoration)

└── [line 496] InventoryTransaction (type=sale_reversal, cost_impact=reversal_cost)
```

### 6.2 Transformation Reversal

```
inventory/services.py:void_transformation()
│
├── For each TransformationItem:
│   │
│   ├── [line 225] item.create_reversal()
│   │   │
│   │   ├── [line 456] source_product.inventory.quantity += 1
│   │   ├── [line 459] source_cost = unit_cost_at_transformation - allocated_service_fee
│   │   ├── [line 460] InventoryTransaction (type=transformation_reversal, cost_impact=source_cost)
│   │   │
│   │   ├── IF consumed_layer is set:
│   │   │   └── [line 470] consumed_layer.remaining_quantity += 1
│   │   │       Original layer restored at its original FIFO position.
│   │   │
│   │   └── IF consumed_layer is NULL (legacy):
│   │       └── Does nothing here; handled below
│   │
│   └── [line 227] IF item.consumed_layer is None:
│       └── _restore_fifo_layer(source_product, 1, source_unit_cost)
│           Creates a new layer at the back of the FIFO queue.
```

### 6.3 Receipt Void

```
supply_chain/services.py:void_and_correct()
│
├── For each GoodsReceiptItem:
│   │
│   ├── [line 150] item.create_reversal(user) → creates reversal receipt item + transaction
│   │
│   ├── [lines 153-155] Looks up the single InventoryCostLayer via goods_receipt_item=item
│   │
│   ├── IF cost_layer.remaining_quantity < item.received_quantity:
│   │   └── [lines 162-165] Raises BusinessRuleViolation
│   │       (cannot void a receipt whose units have already been sold)
│   │
│   └── ELSE:
│       ├── [line 166] cost_layer.is_voided = True
│       ├── [line 167] cost_layer.remaining_quantity = 0
│       └── [line 168] cost_layer.voided_at = timezone.now()
│           Layer is explicitly marked voided rather than anonymously depleted.
│           _deplete_fifo_layers() automatically skips it via is_voided=False filter.
```

### 6.4 Admin Deletion Safety Net

`customer/signals.py:return_inventory_on_sale_deletion` (line 49-78) uses the
same three-tier strategy as `void_sale` to handle BoxedSale deletion via the
Django admin.

---

## 7. LEGACY FALLBACK BEHAVIOUR

### 7.1 Synthetic WAC layer in `_deplete_fifo_layers()`

**Location:** `inventory/services.py:37-67`

When no `InventoryCostLayer` rows exist (or their total `remaining_quantity` is
less than the requested quantity), the function creates a synthetic layer for
the gap using the product's current `Inventory.weighted_average_cost` as
`unit_cost`.

This triggers for products that have quantity in `Inventory` but lack
corresponding cost layers — specifically inventory created before FIFO was
deployed, or stock added outside the `process_receipt` flow.

The synthetic layer is temporary: once legacy stock is fully depleted and all
subsequent inventory arrives through `process_receipt` (which always creates
real layers), the fallback stops triggering.

### 7.2 `cost_basis is NULL` — pre-FIFO sales

`BoxedSale` rows created before FIFO have `cost_basis = NULL`. The `profit`
property (`customer/models.py:1305-1306`) falls back to the WAC formula. On
void, Path C of the reversal logic is taken — quantity is restored but no layer
is touched.

### 7.3 `consumed_layer is NULL` — pre-FIFO transformations

`TransformationItem` rows created before FIFO have `consumed_layer = NULL`. On
void, `create_reversal()` does no layer restoration, and `void_transformation()`
creates a new layer via `_restore_fifo_layer()` as Path B.

### 7.4 `cost_basis` exists but no `layer_consumptions`

Sales created with the FIFO cost basis but before the `BoxedSaleLayerConsumption`
junction model existed are handled by Path B in `void_sale`: a single averaged
layer is created at the back of the FIFO queue using `cost_basis / quantity` as
the unit cost.

---

## 8. DESIGN DECISIONS

### 8.1 `cost_basis` stores total cost, not per-unit

`BoxedSale.cost_basis` is the total across all layers (e.g. `2240.00`), not a
per-unit average (e.g. `224.00`). This avoids any precision loss from division.
The per-unit figure is derivable as `cost_basis / quantity` when needed.

### 8.2 `PROTECT` on `BoxedSaleLayerConsumption.cost_layer`

Prevents accidental deletion of an `InventoryCostLayer` that has sale history
referencing it. This forces explicit handling rather than silent cascade-deletion
of audit records.

### 8.3 `SET_NULL` on `TransformationItem.consumed_layer`

If the referenced `InventoryCostLayer` is deleted, the FK becomes NULL and the
reversal falls back to `_restore_fifo_layer()`. Unlike sale consumption records,
transformation consumption is primarily operational (enabling correct reversal),
not audit-oriented. A `TransformationItem` should survive its layer.

### 8.4 Restoring by incrementing `remaining_quantity` rather than creating new layers

Both `void_sale` (via `BoxedSaleLayerConsumption`) and `create_reversal` (via
`consumed_layer`) restore units by incrementing `remaining_quantity` on the
**original** layer rather than creating new ones. This preserves:

- **FIFO order** — the original layer's `created_at` is unchanged
- **Layer identity** — a purchase batch is a real business object; returned units belong to the same batch
- **Receipt linkage** — `goods_receipt_item` FK remains intact

### 8.5 Lazy synthetic fallback over migration-time backfill

Synthetic layers are created on-demand when stock without cost layers is sold,
rather than running a data migration at deploy time to populate layers for all
existing inventory. This avoids the complexity of reverse-engineering historical
receipt data, accounting for already-sold quantities, and reconciling
inconsistencies. Once legacy stock is depleted through normal operations, the
fallback becomes dormant.

### 8.6 WAC maintained alongside FIFO

`Inventory.weighted_average_cost` continues to be calculated on every receipt.
It powers inventory valuation displays (dashboard, inventory listing) and
provides the fallback cost basis for pre-FIFO sales. FIFO cost layers are the
source of truth for profit calculation. The two metrics serve different purposes
and may diverge, which is expected.

### 8.7 `full_clean()` on `TransformationItem.save()`

The `clean()` method validates type-variant constraints. Calling `full_clean()`
in `save()` ensures these constraints are enforced on programmatic saves (from
services), not only on form submissions.

### 8.8 `is_voided` flag over depleting `remaining_quantity` on receipt void

When a receipt is voided, the associated `InventoryCostLayer` is marked
`is_voided=True` and `remaining_quantity` is set to 0, rather than simply
decrementing `remaining_quantity` by the received amount. This makes the
layer's voided state explicit: decrementing `remaining_quantity` is the same
operation a sale performs, which would make a voided layer visually identical
to a fully-sold layer. The `is_voided` flag allows anyone inspecting the
database to immediately distinguish "this batch was voided" from "this batch
was fully sold." The `_deplete_fifo_layers` query filters `is_voided=False`,
so voided layers are automatically excluded from all consumption paths without
extra checks.

---

## 9. KNOWN LIMITATIONS

### 9.1 No backfill command for legacy cost layers

Inventory created before FIFO uses synthetic WAC-based layers until depleted. A
management command that iterates `GoodsReceiptItem` records and creates
corresponding `InventoryCostLayer` rows (with `remaining_quantity` adjusted for
already-sold units) would eliminate the synthetic fallback for legacy stock.

### 9.2 Receipt void errors identify sold count but not which sales

`void_and_correct` raises `BusinessRuleViolation` with the number of already-sold
units but does not surface which specific sales consumed them. The
`InventoryCostLayer.sale_consumptions` reverse relation could provide this
detail but is not included in the error message.

### 9.3 No `BoxedSaleLayerConsumption` equivalent for coupled sales

Coupled sales use `TransformationItem.unit_cost_at_transformation` (snapshotted
at transformation time, now FIFO-based) for their cost basis. There is no need
for a consumption tracking model on the coupled side because the
`consumed_layer` FK on `TransformationItem` already records which boxed-product
layer was depleted, and the snapped cost is final at that point.

### 9.4 `_deplete_fifo_layers` synthetic fallback and concurrent access

When the synthetic fallback creates a new layer and re-fetches, there is a
theoretical window where another concurrent depletion could target the synthetic
layer. Mitigation: `select_for_update()` on the initial layer query locks
existing layers; the caller holds a separate `select_for_update()` on the
`Inventory` row within the same transaction.

### 9.5 `full_clean()` runs on partial saves

`TransformationItem.save()` calls `full_clean()` even on partial saves like
`save(update_fields=["status"])`. The `clean()` method only validates
`source_product` and `target_product` — fields that do not change after
creation — so the overhead is negligible.
