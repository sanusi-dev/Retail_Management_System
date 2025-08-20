
document.addEventListener('DOMContentLoaded', () => {
   const itemsContainer = document.getElementById('items-container');
   const managementFormPrefix = '{{ item_formset.prefix }}';
   const totalFormsInput = document.getElementById(`id_${managementFormPrefix}-TOTAL_FORMS`);

   const updateFormset = () => {
      const formRows = itemsContainer.querySelectorAll('.item-form-row');
      // Update the TOTAL_FORMS count
      totalFormsInput.value = formRows.length;

      formRows.forEach((row, index) => {
         // Find all input, select, and textarea elements within the row
         const formElements = row.querySelectorAll('input, select, textarea');
         formElements.forEach(el => {
            // Example name: items-1-product -> we want to replace '1' with `index`
            const nameRegex = new RegExp(`(${managementFormPrefix}-\\d+)`);
            // Example id: id_items-1-product -> we want to replace '1' with `index`
            const idRegex = new RegExp(`(id_${managementFormPrefix}-\\d+)`);

            if (el.name) {
               el.name = el.name.replace(nameRegex, `${managementFormPrefix}-${index}`);
            }
            if (el.id) {
               el.id = el.id.replace(idRegex, `id_${managementFormPrefix}-${index}`);
            }
         });
      });
   };

   // --- Event Listeners ---

   // Before HTMX adds a new form, set the correct index for the request
   document.body.addEventListener('htmx:configRequest', (evt) => {
      // Check if the request is coming from our "Add Item" button
      if (evt.detail.elt.id === 'add-item-btn') {
         const formRowCount = itemsContainer.querySelectorAll('.item-form-row').length;
         evt.detail.parameters['index'] = formRowCount;
      }
   });

   // After HTMX adds a new form, update the TOTAL_FORMS count
   document.body.addEventListener('htmx:afterSwap', (evt) => {
      if (evt.target === itemsContainer) {
         // We only need to update the count, no re-indexing is needed on add
         totalFormsInput.value = itemsContainer.querySelectorAll('.item-form-row').length;
      }
   });

   // Handle the removal of form rows
   itemsContainer.addEventListener('click', (e) => {
      if (e.target && e.target.classList.contains('remove-form-row')) {
         e.preventDefault();
         const rowToRemove = e.target.closest('.item-form-row');
         const deleteCheckbox = rowToRemove.querySelector('input[name$="-DELETE"]');

         if (deleteCheckbox) {
            deleteCheckbox.checked = true;
            rowToRemove.style.display = 'none';

            const errorRow = rowToRemove.nextElementSibling;
            if (errorRow && errorRow.classList.contains('item-form-row-errors')) {
               errorRow.style.display = 'none';
            }
         } else {
            const errorRow = rowToRemove.nextElementSibling;
            if (errorRow && errorRow.classList.contains('item-form-row-errors')) {
               errorRow.remove();
            }
            rowToRemove.remove();

            updateFormset();
         }
      }
   });
});