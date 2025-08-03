-- Suppliers Table
CREATE TABLE suppliers (
    supplier_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(255),
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id)
);

-- Purchase Orders Table - Corrected
CREATE TABLE purchase_orders (
    po_id INT PRIMARY KEY AUTO_INCREMENT,
    supplier_id INT NOT NULL,
    po_number VARCHAR(50) UNIQUE NOT NULL,
    order_date DATE NOT NULL,
    expected_delivery_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'Pending Delivery',
    total_amount DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    
    -- Named Constraints
    CONSTRAINT chk_po_status 
        CHECK (status IN ('Pending', 'Approved', 'Partially Received', 'Received', 'Cancelled')),
    
    CONSTRAINT chk_po_delivery_date 
        CHECK (expected_delivery_date >= order_date),
    
    CONSTRAINT chk_po_total_amount 
        CHECK (total_amount > 0)
);

-- Purchase Order Items Table - Corrected
CREATE TABLE purchase_order_items (
    po_item_id INT PRIMARY KEY AUTO_INCREMENT,
    po_id INT NOT NULL,
    product_id INT NOT NULL,
    ordered_quantity INT NOT NULL,
    unit_price_at_order DECIMAL(10, 2) NOT NULL,
    received_quantity INT DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'Pending Delivery',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    
    -- Named Constraints
    CONSTRAINT chk_po_item_status 
        CHECK (status IN ('Pending Delivery', 'Partially Received', 'Received', 'Cancelled')),
    
    CONSTRAINT chk_po_item_positive_values 
        CHECK (ordered_quantity > 0 AND received_quantity >= 0 AND unit_price_at_order > 0),
    
    CONSTRAINT chk_po_item_received_not_exceed_ordered 
        CHECK (received_quantity <= ordered_quantity)
);

-- Supplier Payments Table - Corrected
CREATE TABLE supplier_payments (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    po_id INT NOT NULL,
    amount_paid DECIMAL(10, 2) NOT NULL,
    payment_date DATE NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    transaction_reference VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'Completed',
    remark TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    
    -- Named Constraints
    CONSTRAINT chk_supplier_payment_method 
        CHECK (payment_method IN ('Cash', 'Bank Transfer', 'Cheque', 'Mobile Money')),
    
    CONSTRAINT chk_supplier_payment_status 
        CHECK (status IN ('Completed', 'Pending', 'Failed', 'Cancelled')),
    
    CONSTRAINT chk_positive_payment_amount 
        CHECK (amount_paid > 0)
);

-- Goods Receipts Table - Corrected
CREATE TABLE goods_receipts (
    receipt_id INT PRIMARY KEY AUTO_INCREMENT,
    po_id INT NOT NULL,
    delivery_date DATE NOT NULL,
    received_by INT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id),
    FOREIGN KEY (received_by) REFERENCES users(user_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    
    -- Named Constraints
    CONSTRAINT chk_goods_receipt_status 
        CHECK (status IN ('Pending', 'Completed', 'Cancelled'))
);

-- Goods Receipt Items Table - Corrected
CREATE TABLE goods_receipt_items (
    receipt_item_id INT PRIMARY KEY AUTO_INCREMENT,
    receipt_id INT NOT NULL,
    po_item_id INT NOT NULL,
    product_id INT NOT NULL,
    actual_product_id INT NOT NULL,    -- What you actually received
    received_quantity INT NOT NULL,
    serial_item_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (receipt_id) REFERENCES goods_receipts(receipt_id),
    FOREIGN KEY (po_item_id) REFERENCES purchase_order_items(po_item_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (actual_product_id) REFERENCES products(product_id),
    FOREIGN KEY (serial_item_id) REFERENCES serialized_inventory_items(serial_item_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    
    -- Named Constraints
    CONSTRAINT chk_receipt_item_positive_quantity 
        CHECK (received_quantity > 0)
);