-- Sales Table - Corrected
CREATE TABLE sales (
    sale_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    sale_date DATE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    
    -- Named Constraints
    CONSTRAINT chk_sale_status 
        CHECK (status IN ('Pending', 'Completed', 'Cancelled', 'Voided'))
);

-- Sale Items Table - Corrected
CREATE TABLE sale_items (
    sale_item_id INT PRIMARY KEY AUTO_INCREMENT,
    sale_id INT NOT NULL,
    product_id INT NOT NULL,
    sold_quantity INT NOT NULL,
    unit_selling_price DECIMAL(10, 2) NOT NULL,
    serial_item_id INT,
    status VARCHAR(50) NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (sale_id) REFERENCES sales(sale_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (serial_item_id) REFERENCES serialized_inventory_items(serial_item_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    
    -- Named Constraints
    CONSTRAINT chk_sale_item_status 
        CHECK (status IN ('Pending', 'Fulfilled', 'Cancelled', 'Voided')),
    
    CONSTRAINT chk_sale_item_positive_values 
        CHECK (sold_quantity > 0 AND unit_selling_price > 0)
);

-- Customer Transactions Table - Corrected
CREATE TABLE customer_transactions (
    transaction_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    sale_id INT,                             -- Only for sales transactions
    transaction_type VARCHAR(50) NOT NULL,   -- 'Deposit', 'Withdrawal', 'Sale Payment'
    amount DECIMAL(10, 2) NOT NULL,          -- Always positive value
    flow_direction VARCHAR(10) NOT NULL,     -- 'In' or 'Out' 
    deposit_purpose VARCHAR(50),             -- Only for deposits: 'Normal Deposit', 'Buy Goods', 'Convert to CFA'
    payment_method VARCHAR(50) NOT NULL,     -- Cash, Transfer, etc.
    transaction_reference VARCHAR(255),
    transaction_date DATE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Completed',
    remark TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (sale_id) REFERENCES sales(sale_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    
    -- Named Constraints
    CONSTRAINT chk_transaction_type 
        CHECK (transaction_type IN ('Deposit', 'Withdrawal', 'Sale Payment')),
    
    CONSTRAINT chk_flow_direction 
        CHECK (flow_direction IN ('In', 'Out')),
    
    CONSTRAINT chk_deposit_purpose_logic 
        CHECK (
            (transaction_type = 'Deposit' AND deposit_purpose IS NOT NULL) OR 
            (transaction_type != 'Deposit' AND deposit_purpose IS NULL)
        ),
    
    CONSTRAINT chk_sale_payment_logic 
        CHECK (
            (transaction_type = 'Sale Payment' AND sale_id IS NOT NULL) OR
            (transaction_type != 'Sale Payment' AND sale_id IS NULL)
        ),
    
    CONSTRAINT chk_payment_method 
        CHECK (payment_method IN ('Cash', 'Bank Transfer', 'Mobile Money', 'Cheque')),
    
    CONSTRAINT chk_positive_amount 
        CHECK (amount > 0),
    
    CONSTRAINT chk_deposit_purpose_values 
        CHECK (deposit_purpose IN ('Normal Deposit', 'Buy Goods', 'Convert to CFA'))
);