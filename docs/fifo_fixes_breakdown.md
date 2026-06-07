# FIFO Fixes — Technical Breakdown

## Overview

Three fixes address granularity, integrity, and correctness issues in the FIFO implementation. All changes were verified against the existing test suite (8/8 `test_new_sale_system`, 38/38 `test_financial_logic`, 5/5 `supply_chain`).

---

## FIX 1 — SALE REVERSAL LAYER GRANULARITY (HIGHEST PRIORITY)

### Problem

When `void_sale` was called on a `BoxedSale` that consumed units from multiple `InventoryCostLayer` rows, the previous code merged them into a single averaged layer via `_restore_fifo_layer()`. This lost:
- Individual layer identity (distinct 200 vs 260 cost layers were collapsed into one 224 layer)
- FIFO chronological order (the restored unit went to the back of the queue with a new `created_at`)

### New Model: `BoxedSaleLayerConsumption`

**File:** `customer/models.py:1129-1154`

```python
class BoxedSaleLayerConsumption(models.Model):
    boxed_sale = models.ForeignKey("BoxedSale", on_delete=models.CASCADE, related_name="layer_consumptions")
    cost_layer = models.ForeignKey(InventoryCostLayer, on_delete=models.PROTECT, related_name="sale_consumptions")
    quantity_consumed = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
```

- `on_delete=CASCADE` on `boxed_sale`: if the sale is deleted, its consumption records are cleaned up automatically.
- `on_delete=PROTECT` on `cost_layer`: prevents accidental deletion of a layer that has sale history referencing it.
- `unit_cost` is snapshotted at consumption time (matches the `InventoryCostLayer.unit_cost` value at depletion).

### Modified: `_deplete_fifo_layers()` — return type change

**File:** `inventory/services.py:15-93`
**Method:** `_deplete_fifo_layers(product, quantity)`
**Before:** returned `total_cost` (a `Decimal`)
**After:** returns `(total_cost, consumption_entries)` (a tuple)

Each `consumption_entries` element is a dict:
```python
{"layer": InventoryCostLayer instance, "quantity": int, "unit_cost": Decimal}
```

The function now builds a `consumption_entries` list at line 71, appending entries during the depletion loop at lines 80-84:

```python
consumption_entries.append({
    "layer": layer,
    "quantity": take,
    "unit_cost": layer.unit_cost,
})
```

The return statement at line 93 is:
```python
return total_cost, consumption_entries
```

### Modified: `create_sale()` — recording consumption records

**File:** `customer/services.py:364-375`
**Method:** `create_sale()`

After the `_deplete_fifo_layers()` call returns, the function now iterates the `consumptions` list and creates one `BoxedSaleLayerConsumption` row per consumed layer:

```python
fifo_cost, consumptions = _deplete_fifo_layers(item.product, item.quantity)
item.cost_basis = fifo_cost
item.save(update_fields=["cost_basis"])

for entry in consumptions:
    BoxedSaleLayerConsumption.objects.create(
        boxed_sale=item,
        cost_layer=entry["layer"],
        quantity_consumed=entry["quantity"],
        unit_cost=entry["unit_cost"],
    )
```

The `BoxedSaleLayerConsumption` import was added to the inline imports at line 341.

### Modified: `void_sale()` — restoring original layers

**File:** `customer/services.py:479-494`
**Method:** `void_sale()`

Three-tier reversal strategy, evaluated in priority order:

1. **Consumption records exist** (lines 480-486): iterate `boxed_sale.layer_consumptions.all()`. For each record, increment `remaining_quantity` on the **original** `InventoryCostLayer` directly. This preserves the layer's `created_at` and its position in FIFO order.

2. **Only `cost_basis` exists** (lines 487-492): legacy sales recorded after the initial FIFO implementation but before this fix. Falls back to `_restore_fifo_layer()` (creates a new averaged layer).

3. **Neither exists** (lines 493-494): pre-FIFO sales. Uses `inventory.weighted_average_cost` with no layer restoration.

```python
consumptions = boxed_sale.layer_consumptions.all()
if consumptions.exists():
    reversal_cost = Decimal("0.00")
    for c in consumptions:
        c.cost_layer.remaining_quantity += c.quantity_consumed
        c.cost_layer.save(update_fields=["remaining_quantity"])
        reversal_cost += Decimal(str(c.quantity_consumed)) * c.unit_cost
elif boxed_sale.cost_basis is not None:
    from inventory.services import _restore_fifo_layer
    reversal_cost = boxed_sale.cost_basis
    unit_cost = boxed_sale.cost_basis / boxed_sale.quantity
    _restore_fifo_layer(boxed_sale.product, boxed_sale.quantity, unit_cost)
else:
    reversal_cost = inventory.weighted_average_cost * boxed_sale.quantity
```

### Modified: `customer/signals.py` — admin deletion safety net

**File:** `customer/signals.py:49-78`
**Signal:** `return_inventory_on_sale_deletion` (post_delete on `BoxedSale`)

Uses the same three-tier strategy as `void_sale`. The `_restore_fifo_layer` call is now lazily imported inside the legacy fallback branch (line 65) since it's no longer needed in the primary code path.

A `from decimal import Decimal` import was added at line 5 since the handler now explicitly constructs `Decimal("0.00")`.

### Removed

- Direct call to `_restore_fifo_layer()` from `void_sale` in the primary code path (replaced by layer iteration).
- The import of `_restore_fifo_layer` from `void_sale`'s local imports (line 459).

---

## FIX 2 — TRANSFORMATIONITEM FK RESTRICTION (MEDIUM PRIORITY)

### Problem

`TransformationItem.source_product` and `target_product` were unrestricted `ForeignKey` fields to `Product`. Nothing prevented:
- Setting `source_product` to a coupled product
- Setting `target_product` to a boxed product

### Model field changes

**File:** `inventory/models.py:387-400`
**Model:** `TransformationItem`

`source_product` (line 387-392): added `limit_choices_to={"type_variant": Product.TypeVariant.BOXED}`

`target_product` (line 393-400): added `limit_choices_to={"type_variant": Product.TypeVariant.COUPLED}`

### New method: `clean()`

**File:** `inventory/models.py:444-452`
**Method:** `TransformationItem.clean()`

```python
def clean(self):
    if self.source_product and self.source_product.type_variant != Product.TypeVariant.BOXED:
        raise ValidationError(
            {"source_product": "Source product must be a boxed variant."}
        )
    if self.target_product and self.target_product.type_variant != Product.TypeVariant.COUPLED:
        raise ValidationError(
            {"target_product": "Target product must be a coupled variant."}
        )
```

- Guards are null-safe: only checks if the FK value is already set.
- Uses `ValidationError` with field-keyed dict so error messages appear next to the correct form field.

### Modified: `save()`

**File:** `inventory/models.py:476-479`
**Method:** `TransformationItem.save()`

Now calls `self.full_clean()`:

```python
def save(self, *args, **kwargs):
    if not self.item_number:
        self.item_number = f"ITEM-{uuid.uuid4().hex[:8].upper()}"
    self.full_clean()
    super().save(*args, **kwargs)
```

Previously, `save()` did **not** call `full_clean()`. The `clean()` from the model was only triggered by ModelForm validation. Adding `full_clean()` to `save()` ensures programmatic saves (e.g., from services or Django admin) also get validated.

**Note:** this means `full_clean()` runs on every save, including field-specific updates like `save(update_fields=["status"])`. The `clean()` method only validates `source_product` and `target_product` — it does not add other model-level constraints, so repeated validation on partial updates is harmless.

---

## FIX 3 — TRANSFORMATION REVERSAL FIFO POSITION (LOW PRIORITY)

### Problem

When a `TransformationItem` was voided via `create_reversal()`, `void_transformation()` called `_restore_fifo_layer()` to create a brand new `InventoryCostLayer` with `created_at=now()`. This placed the restored unit at the **back** of the FIFO queue instead of its original chronological position. If the transformation was from an old cost layer, the restored unit would now appear to be "newer" than inbound receipts that arrived after the original transformation.

### New field: `TransformationItem.consumed_layer`

**File:** `inventory/models.py:413-420`

```python
consumed_layer = models.ForeignKey(
    InventoryCostLayer,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="transformation_consumptions",
    help_text="The FIFO cost layer consumed during this transformation",
)
```

- `on_delete=SET_NULL`: if the `InventoryCostLayer` is removed, the FK becomes NULL rather than deleting the `TransformationItem`.
- `null=True, blank=True`: legacy `TransformationItem` rows created before this fix will have `consumed_layer=NULL`.
- `related_name="transformation_consumptions"`: inverse accessor from `InventoryCostLayer` to its consumed items.

### Modified: `process_transformation()` — recording consumed layer

**File:** `inventory/services.py:174-179`
**Method:** `process_transformation()`

After `_deplete_fifo_layers()` returns the consumption entries, the first (and only, since transformation always uses quantity=1) entry's layer is recorded:

```python
fifo_cost, consumptions = _deplete_fifo_layers(item.source_product, 1)
item.unit_cost_at_transformation = fifo_cost + service_fee_per_item
if consumptions:
    item.consumed_layer = consumptions[0]["layer"]
```

The guard `if consumptions:` handles the degenerate case where `_deplete_fifo_layers` returns an empty list (should not happen in normal operation since the function raises `BusinessRuleViolation` on failure, but defensive coding).

### Modified: `create_reversal()` — restoring to original layer

**File:** `inventory/models.py:454-474`
**Method:** `TransformationItem.create_reversal()`

New logic at lines 468-471:

```python
# Restore to original FIFO layer if tracked (Fix 3)
if self.consumed_layer:
    self.consumed_layer.remaining_quantity += 1
    self.consumed_layer.save(update_fields=["remaining_quantity"])
```

When `consumed_layer` is set, the method increments `remaining_quantity` on the **original** layer directly. This:
- Preserves the layer's `created_at` (FIFO order is maintained)
- Preserves the layer's `unit_cost` (no averaging)
- Avoids creating a new layer

The `InventoryTransaction` reversal at lines 459-466 continues to use `source_cost = self.unit_cost_at_transformation - self.allocated_service_fee` for `cost_impact`, which matches the cost that was originally depleted.

### Modified: `void_transformation()` — legacy fallback only

**File:** `inventory/services.py:222-229`
**Method:** `void_transformation()`

Changed from always calling `_restore_fifo_layer` to only doing so when `consumed_layer is None` (legacy):

```python
item.create_reversal()
# Legacy fallback: if consumed_layer was not tracked, create a new layer (Fix 3)
if item.consumed_layer is None:
    source_unit_cost = item.unit_cost_at_transformation - item.allocated_service_fee
    _restore_fifo_layer(item.source_product, 1, source_unit_cost)
```

For new transformations (Fix 3+), `create_reversal()` now handles the layer restoration internally, so `void_transformation` skips calling `_restore_fifo_layer`.

### Edge cases handled

| Case | Behavior |
|------|----------|
| `consumed_layer` is set (new transformations) | `create_reversal()` increments `remaining_quantity` on original layer; `void_transformation` does nothing extra |
| `consumed_layer` is NULL (legacy transformations) | `void_transformation` calls `_restore_fifo_layer()` to create a new layer |
| `consumed_layer` FK target is deleted | `SET_NULL` makes `consumed_layer=None`; item voids into a new layer via the legacy fallback |
| Syntactic layer fallback (no real FIFO layers at transformation time) | `_deplete_fifo_layers` creates a synthetic layer; `consumed_layer` points to it; void goes back to that same synthetic layer |

---

## Summary of All Changes by File

### `inventory/models.py`
| Change | Lines | Type |
|--------|-------|------|
| `source_product` → add `limit_choices_to` | 387-392 | Fix 2 |
| `target_product` → add `limit_choices_to` | 393-400 | Fix 2 |
| `consumed_layer` FK → new field | 413-420 | Fix 3 |
| `clean()` → new method | 444-452 | Fix 2 |
| `create_reversal()` → restore original layer | 468-471 | Fix 3 |
| `save()` → call `full_clean()` | 476-479 | Fix 2 |

### `inventory/services.py`
| Change | Lines | Type |
|--------|-------|------|
| `_deplete_fifo_layers()` → return tuple | 15-93 | Foundation for Fix 1+3 |
| `process_transformation()` → unpack tuple | 175 | Foundation for Fix 1+3 |
| `process_transformation()` → record `consumed_layer` | 178-179 | Fix 3 |
| `void_transformation()` → legacy fallback only | 227-229 | Fix 3 |

### `customer/models.py`
| Change | Lines | Type |
|--------|-------|------|
| Import `InventoryCostLayer` | 23 | Fix 1 |
| `BoxedSaleLayerConsumption` model | 1129-1154 | Fix 1 |

### `customer/services.py`
| Change | Lines | Type |
|--------|-------|------|
| `create_sale()` → import `BoxedSaleLayerConsumption` | 341 | Fix 1 |
| `create_sale()` → unpack tuple | 364 | Foundation for Fix 1 |
| `create_sale()` → create consumption records | 369-375 | Fix 1 |
| `void_sale()` → restore original layers via consumptions | 479-494 | Fix 1 |
| `void_sale()` → remove `_restore_fifo_layer` import | 459 | Fix 1 |

### `customer/signals.py`
| Change | Lines | Type |
|--------|-------|------|
| Import `Decimal` | 5 | Fix 1 |
| `return_inventory_on_sale_deletion` → three-tier strategy | 57-70 | Fix 1 |
| Remove top-level `_restore_fifo_layer` import | 14 | Fix 1 |

### Migrations Generated
| Migration | App | Content |
|-----------|-----|---------|
| `0008_transformationitem_consumed_layer_and_more` | inventory | `consumed_layer` FK, `source_product`/`target_product` `limit_choices_to` alter |
| `0036_boxedsalelayerconsumption` | customer | `BoxedSaleLayerConsumption` model |
