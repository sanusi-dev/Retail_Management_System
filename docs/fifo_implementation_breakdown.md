# FIFO Implementation Breakdown

## 1. Coupled Product Cost Basis

### How is `unit_cost_at_transformation` determined?

It is now the **FIFO cost of the source boxed product plus the allocated service fee**:

```
unit_cost_at_transformation = fifo_cost + service_fee_per_item
```

This is set in `inventory/services.py:166-167` inside `process_transformation()`:

```python
fifo_cost = _deplete_fifo_layers(item.source_product, 1)
item.unit_cost_at_transformation = fifo_cost + service_fee_per_item
```

Previously this was:
```python
item.unit_cost_at_transformation = (
    item.source_product.inventory.weighted_average_cost
    + service_fee_per_item
)
```

So instead of the live WAC, it now uses the actual cost of the oldest FIFO layer(s) consumed from the boxed product's inventory.

### Does the transformation flow consume FIFO cost layers?

**Yes.** `process_transformation` in `inventory/services.py:166` calls `_deplete_fifo_layers(item.source_product, 1)` for each transformation item. This function (at `inventory/services.py:15-84`) iterates over `InventoryCostLayer` records for the source boxed product ordered by `created_at` ASC (oldest first), decrements `remaining_quantity` on each layer, and returns the total cost of the depleted unit(s).

### What method handles this?

The call chain is:

1. `process_transformation()` at `inventory/services.py:116` — the service function
2. Which calls `_deplete_fifo_layers(product, quantity)` at `inventory/services.py:15`
3. The `InventoryTransaction` created at `inventory/services.py:173-179` records `cost_impact=fifo_cost` (the FIFO cost without service fee)
4. The `TransformationItem` stores `unit_cost_at_transformation = fifo_cost + service_fee_per_item` (the full landed cost including assembly) at `inventory/services.py:167`

---

## 2. Coupled Sale Profit

### What cost figure is used to calculate profit?

**`TransformationItem.unit_cost_at_transformation`** — the snapshotted cost from transformation time.

### Where is this calculated?

In `customer/models.py:1122-1126`, the `CoupledSale.profit` property:

```python
@property
def profit(self):
    cost = self.transformation_item.unit_cost_at_transformation or Decimal("0.00")
    price = self.price or Decimal("0.00")
    return price - cost
```

This was **not changed** by the FIFO implementation. Coupled sales have always used the snapshotted `unit_cost_at_transformation` from transformation time. The FIFO change only affects **what value gets written into** `unit_cost_at_transformation` during transformation (see Question 1).

The `product_detail` view at `inventory/views.py:406-409` mirrors this same logic:

```python
coupled_profit = Decimal("0.00")
for cs in coupled_sales:
    cost = cs.transformation_item.unit_cost_at_transformation or Decimal("0.00")
    coupled_profit += (cs.price - cost)
```

---

## 3. Legacy Stock and the Synthetic WAC Layer

### Does all existing stock still use the skewed WAC?

**Yes, initially.** For any product that existed before the FIFO migration (or was created outside the receipt flow, e.g. via Django admin), there are no `InventoryCostLayer` records. When those units are sold, the system falls back to creating a synthetic layer using the **current** `Inventory.weighted_average_cost` at the moment of sale.

### When is this synthetic layer created?

**Lazily, at the time of the first sale or transformation** that hits a product with insufficient FIFO layers. It is not created at migration time.

The logic is in `_deplete_fifo_layers()` at `inventory/services.py:37-64`:

```python
total_available = sum(l.remaining_quantity for l in layers)

if total_available < quantity:
    # Fallback: no (or insufficient) FIFO layers — use current WAC for the gap
    inventory = product.inventory
    wac = inventory.weighted_average_cost

    if inventory.quantity < quantity:
        raise BusinessRuleViolation(...)

    gap = quantity - total_available
    # Create a synthetic layer for the uncovered portion (legacy inventory)
    InventoryCostLayer.objects.create(
        product=product,
        quantity=gap,
        remaining_quantity=gap,
        unit_cost=wac,
    )
    # Re-fetch layers to include the new synthetic one
    layers = (
        InventoryCostLayer.objects.filter(
            product=product,
            remaining_quantity__gt=0,
        )
        .order_by("created_at")
        .select_for_update()
    )
```

The synthetic layer's `unit_cost` is set to the product's current `Inventory.weighted_average_cost` at the moment the sale is recorded. Since this WAC may itself be a skewed average of old and new purchases, **legacy inventory sold before any new receipt arrives will still reflect the old cost basis.** Only after a product goes through `process_receipt` (which creates a proper FIFO layer at `supply_chain/services.py:95-101` with the receipt's actual `unit_cost_at_receipt`) will future sales use accurate costs.

### Is there a management command or migration to backfill real cost layers?

**No.** There is no automatic backfill. The existing `InventoryCostLayer` migration (`inventory/migrations/0007_inventorycostlayer.py`) only creates the table — it does not populate rows.

To properly backfill, you would need a management command that:
1. Iterates all `Inventory` records where `quantity > 0`
2. Finds the corresponding `GoodsReceiptItem` rows (ordered by date) and creates `InventoryCostLayer` rows with the correct `unit_cost_at_receipt`
3. Trims `remaining_quantity` on older layers to account for already-sold stock

Without this command, legacy inventory will be costed at the current (possibly skewed) WAC until it is fully depleted and replaced by new receipts.

---

## 4. Partial Layer Consumption

### Example: Sale of 10 units spanning two layers (6 @ 200, 4 @ 260)

The function `_deplete_fifo_layers()` at `inventory/services.py:66-84` handles this with a simple loop:

```python
remaining_to_deplete = quantity     # starts at 10
total_cost = Decimal("0.00")

for layer in layers:
    if remaining_to_deplete <= 0:
        break
    take = min(layer.remaining_quantity, remaining_to_deplete)
    layer.remaining_quantity -= take
    layer.save(update_fields=["remaining_quantity"])
    total_cost += Decimal(str(take)) * layer.unit_cost
    remaining_to_deplete -= take
```

Step-by-step for your scenario:

| Iteration | Layer | `remaining` before | `take` | `remaining` after | `total_cost` so far |
|-----------|-------|--------------------|--------|-------------------|---------------------|
| 1 | 1 (cost 200) | 6 | 6 | 0 | 6 × 200 = 1,200 |
| 2 | 2 (cost 260) | 4 | 4 | 0 | 1,200 + (4 × 260) = 2,240 |

After the loop: `remaining_to_deplete` = 0, so the final `if remaining_to_deplete > 0` check passes. The function returns `Decimal("2240.00")`.

### What is the resulting `cost_basis` stored on `BoxedSale`?

**The raw sum: `2240.00`.** It is stored at `customer/services.py:363-364`:

```python
fifo_cost = _deplete_fifo_layers(item.product, item.quantity)
item.cost_basis = fifo_cost
```

This is the **total** actual cost across all layers consumed, **not** a weighted average per unit. The `BoxedSale.profit` property at `customer/models.py:1275-1276` subtracts this total from total revenue:

```python
if self.cost_basis is not None:
    return (price * self.quantity) - self.cost_basis
```

So for a sale of 10 units at price 320 each: profit = (320 × 10) − 2240 = 3200 − 2240 = **960**.

---

## 5. Transformation Reversal

### Has `create_reversal()` been updated?

**Yes.** Previously it used `inventory.weighted_average_cost` for the reversal transaction's `cost_impact`. Now it derives the source cost from the snapshotted `unit_cost_at_transformation`.

In `inventory/models.py:432-446`:

```python
def create_reversal(self):
    inventory = self.source_product.inventory
    inventory.quantity += 1
    inventory.save(update_fields=["quantity"])

    source_cost = self.unit_cost_at_transformation - self.allocated_service_fee
    create_inventory_transaction(
        inventory=inventory,
        source=self,
        transaction_type=InventoryTransaction.TransactionType.TRANSFORMATION_REVERSAL,
        quantity_change=1,
        cost_impact=source_cost,
    )
    self.status = self.Status.VOIDED
    self.save(update_fields=["status"])
```

The `source_cost` at line 437 strips the service fee from the snapshotted cost, recovering the original FIFO cost that was depleted at transformation time.

### Does it restore the correct FIFO layer?

**Yes, but as a new layer at the back of the queue.** After `create_reversal()` runs, `void_transformation()` at `inventory/services.py:213-216` also restores the FIFO layer:

```python
item.create_reversal()
# Restore FIFO layer for the source product at original cost
source_unit_cost = item.unit_cost_at_transformation - item.allocated_service_fee
_restore_fifo_layer(item.source_product, 1, source_unit_cost)
```

`_restore_fifo_layer()` at `inventory/services.py:87-99` creates a **brand new** `InventoryCostLayer`:

```python
def _restore_fifo_layer(product, quantity, unit_cost):
    InventoryCostLayer.objects.create(
        product=product,
        quantity=quantity,
        remaining_quantity=quantity,
        unit_cost=unit_cost,
    )
```

Key implications:
- The **unit cost** is correct: it matches the original FIFO cost from transformation time (snapshotted in `unit_cost_at_transformation` minus `allocated_service_fee`).
- The **FIFO position** is at the **end** of the queue: the new layer gets `created_at=now()`, so it will be depleted after all existing layers. It does not re-enter the queue at its original chronological position.
- The `InventoryTransaction` records this as `cost_impact = source_cost` (matching the restored layer).

---

## 6. Sale Reversal

### Does `void_sale` restore the exact FIFO layers in the correct order?

**No.** It does not restore the original layers in their original FIFO positions. Instead, it creates a **single new aggregated layer** at the **back** of the FIFO queue.

The relevant code is in `customer/services.py:470-474`:

```python
if boxed_sale.cost_basis is not None:
    reversal_cost = boxed_sale.cost_basis
    unit_cost = boxed_sale.cost_basis / boxed_sale.quantity
    _restore_fifo_layer(boxed_sale.product, boxed_sale.quantity, unit_cost)
else:
    reversal_cost = inventory.weighted_average_cost * boxed_sale.quantity
```

### What this means in practice

Suppose a sale consumed:
- 6 units from layer 1 at cost 200
- 4 units from layer 2 at cost 260  
→ `cost_basis` = 2240, `unit_cost` = 2240/10 = 224

When voided:
1. Inventory quantity is incremented by 10 (`customer/services.py:467-468`)
2. A **single new layer** is created with `quantity=10, remaining_quantity=10, unit_cost=224`
3. This layer is at the **back** of the FIFO queue (new `created_at`)
4. The reversal `InventoryTransaction` records `cost_impact=2240` (`customer/services.py:478-484`)

### Layer integrity assessment

| Aspect | Status | Detail |
|--------|--------|--------|
| Total cost | **Correct** | `cost_basis` (2240) = original total consumed |
| Average unit cost | **Correct** | 224 = 2240/10 |
| Individual layer costs | **Lost** | The distinct 200 and 260 layers are merged into one |
| FIFO order | **Approximate** | Restored units go to the back, not their original positions |
| Inventory quantity | **Correct** | Quantity restored by the full 10 |

The simplification is intentional: tracking per-sale which specific layers were consumed would require a many-to-many relationship between `BoxedSale` and `InventoryCostLayer`, adding significant complexity. The current approach preserves the correct total cost basis, and the FIFO order approximation is acceptable because voided+restored units typically represent returned or mistaken stock that should be treated as "new arrivals" in inventory order.
