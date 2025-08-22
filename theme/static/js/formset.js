
document.addEventListener('DOMContentLoaded', () => {
   const itemsContainer = document.getElementById('items-container');
   const totalFormsInput = document.querySelector('input[name$="-TOTAL_FORMS"]');


   // Extract the prefix from the TOTAL_FORMS input name
   const managementFormPrefix = totalFormsInput.name.replace('-TOTAL_FORMS', '');

   const updateFormset = () => {
      const formRows = itemsContainer.querySelectorAll('.item-form-row');

      // Update the TOTAL_FORMS count
      totalFormsInput.value = formRows.length;

      formRows.forEach((row, index) => {
         // Find all input, select, and textarea elements within the row
         const formElements = row.querySelectorAll('input, select, textarea');

         formElements.forEach(el => {
            // Update name attribute: items-1-product -> items-0-product
            if (el.name && el.name.includes(`${managementFormPrefix}-`)) {
               el.name = el.name.replace(/(-\d+-)/, `-${index}-`);
            }

            // Update id attribute: id_items-1-product -> id_items-0-product
            if (el.id && el.id.includes(`id_${managementFormPrefix}-`)) {
               el.id = el.id.replace(/(id_\w+-\d+-)/, `id_${managementFormPrefix}-${index}-`);
            }
         });
      });
   };

   // Before HTMX adds a new form, set the correct index for the request
   document.body.addEventListener('htmx:configRequest', (evt) => {
      if (evt.detail.elt.id === 'add-item-btn') {
         const formRowCount = itemsContainer.querySelectorAll('.item-form-row').length;
         evt.detail.parameters['index'] = formRowCount;
      }
   });

   // After HTMX adds a new form, update the TOTAL_FORMS count
   document.body.addEventListener('htmx:afterSwap', (evt) => {
      if (evt.target === itemsContainer) {
         totalFormsInput.value = itemsContainer.querySelectorAll('.item-form-row').length;
      }
   });

   // Handle the removal of form rows
   itemsContainer.addEventListener('click', (e) => {
      const removeButton = e.target.closest('.remove-form-row');

      if (removeButton) {
         e.preventDefault();
         const rowToRemove = removeButton.closest('.item-form-row');
         const deleteCheckbox = rowToRemove.querySelector('input[name$="-DELETE"]');

         if (deleteCheckbox) {
            // For existing forms, mark as deleted and hide
            deleteCheckbox.checked = true;
            rowToRemove.style.display = 'none';
         } else {
            // For new forms, remove entirely and reindex
            rowToRemove.remove();
            updateFormset();
         }
      }
   });
});