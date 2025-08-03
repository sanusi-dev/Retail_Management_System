-- Loans Table - Corrected
CREATE TABLE loans (
    loan_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    sale_id INT,
    loan_type VARCHAR(50) NOT NULL,
    principal_amount DECIMAL(10, 2) NOT NULL,
    loan_date DATE NOT NULL,
    due_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'Active',
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
    CONSTRAINT chk_loan_type_sale_logic 
        CHECK (
            (loan_type = 'Sales Loan' AND sale_id IS NOT NULL) OR 
            (loan_type = 'Normal Loan' AND sale_id IS NULL)
        ),
    
    CONSTRAINT chk_loan_type 
        CHECK (loan_type IN ('Normal Loan', 'Sales Loan')),
    
    CONSTRAINT chk_loan_status 
        CHECK (status IN ('Active', 'Paid', 'Overdue', 'Written Off', 'Cancelled')),
    
    CONSTRAINT chk_positive_principal_amount 
        CHECK (principal_amount > 0),
    
    CONSTRAINT chk_due_date_logic 
        CHECK (due_date IS NULL OR due_date >= loan_date)
);

-- Loan Repayments Table - Corrected
CREATE TABLE loan_repayments (
    repayment_id INT PRIMARY KEY AUTO_INCREMENT,
    loan_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    repayment_date DATE NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    transaction_reference VARCHAR(255),
    remark TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by INT,
    updated_by INT,
    
    -- Foreign Keys
    FOREIGN KEY (loan_id) REFERENCES loans(loan_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (updated_by) REFERENCES users(user_id),
    
    -- Named Constraints
    CONSTRAINT chk_repayment_payment_method 
        CHECK (payment_method IN ('Cash', 'Bank Transfer', 'Mobile Money', 'Cheque')),
    
    CONSTRAINT chk_positive_repayment_amount 
        CHECK (amount > 0)
);