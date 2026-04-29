# All signals in this file have been migrated to supply_chain/services.py
# PO status updates now happen explicitly in service functions:
#   - process_receipt() → updates PO delivery and overall status
#   - void_and_correct() → updates PO delivery and overall status
#   - record_supplier_payment() → updates PO payment and overall status
#   - void_supplier_payment() → updates PO payment and overall status
