-- Products: Added base_product for variants
CREATE TABLE products (
    product_id INT PRIMARY KEY AUTO_INCREMENT,
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    type_variant VARCHAR(50) NOT NULL DEFAULT 'boxed',
    description TEXT,
    base_product_id INT NULL COMMENT 'For variant linking (e.g., boxed->coupled)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Named constraints
    CONSTRAINT fk_products_created_by FOREIGN KEY (created_by) REFERENCES users(user_id),
    CONSTRAINT fk_products_updated_by FOREIGN KEY (updated_by) REFERENCES users(user_id),
    CONSTRAINT fk_products_base_product FOREIGN KEY (base_product_id) REFERENCES products(product_id),
    CONSTRAINT chk_products_type_variant CHECK (type_variant IN ('boxed', 'coupled', 'spare_parts', 'grinding_machine'))
);

-- Bulk Inventory: Unchanged
CREATE TABLE inventory (
    inventory_id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT UNIQUE NOT NULL,
    quantity_on_hand INT NOT NULL DEFAULT 0,
    location VARCHAR(255),
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Named constraints
    CONSTRAINT fk_inventory_product FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- Serialized Inventory: Added product_type constraint
CREATE TABLE serialized_inventory_items (
    serial_item_id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    engine_number VARCHAR(255) UNIQUE,
    chassis_number VARCHAR(255) UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'Available',
    received_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Named constraints
    CONSTRAINT fk_serialized_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT fk_serialized_created_by FOREIGN KEY (created_by) REFERENCES users(user_id),
    CONSTRAINT fk_serialized_updated_by FOREIGN KEY (updated_by) REFERENCES users(user_id),
    CONSTRAINT chk_serialized_numbers CHECK ((engine_number IS NOT NULL AND chassis_number IS NOT NULL)),
    CONSTRAINT chk_serialized_status CHECK (status IN ('Available', 'Sold', 'Reserved', 'Damaged'))
);

-- Inventory Transformation Table (NEW)
CREATE TABLE inventory_transformations (
    transformation_id INT PRIMARY KEY AUTO_INCREMENT,
    boxed_product_id INT NOT NULL,
    coupled_product_id INT NOT NULL,
    engine_number VARCHAR(255) NOT NULL,
    chassis_number VARCHAR(255) NOT NULL,
    transformation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT NOT NULL,
    
    -- Named constraints
    CONSTRAINT fk_transform_boxed_product FOREIGN KEY (boxed_product_id) REFERENCES products(product_id),
    CONSTRAINT fk_transform_coupled_product FOREIGN KEY (coupled_product_id) REFERENCES products(product_id),
    CONSTRAINT fk_transform_created_by FOREIGN KEY (created_by) REFERENCES users(user_id),
    CONSTRAINT uk_transform_serial_numbers UNIQUE (engine_number, chassis_number)
);