def create_inventory_transaction(
    inventory,
    source,
    transaction_type,
    quantity_change,
    cost_impact,
):
    from inventory.models import InventoryTransaction

    return InventoryTransaction.objects.create(
        inventory=inventory,
        source=source,
        transaction_type=transaction_type,
        quantity_change=quantity_change,
        cost_impact=cost_impact,
        created_by=getattr(source, "created_by", None),
        updated_by=getattr(source, "created_by", None),
    )
