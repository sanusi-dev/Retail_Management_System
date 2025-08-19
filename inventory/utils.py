def has_any_children(product):
    product_child_list = [
         'purchase_order_items', 
         'receipt_items_as_product', 
         'receipt_items_as_actual_product', 
         'sale_items', 
         'variants', 
         'inventories', 
         'serialized_products', 
         'boxed_products', 
         'coupled_products'
    ]

    for child in product_child_list:
        if hasattr(product, child) and getattr(product, child).exists():
            return True
    return False



