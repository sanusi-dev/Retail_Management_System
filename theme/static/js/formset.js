// --- LOGIC FOR ADDING A NEW FORM ---
document.body.addEventListener('htmx:configRequest', function (event) {
   const triggerElement = event.detail.elt;

   // Check if the element that triggered the request is an "add row" button
   if (triggerElement.classList.contains('add-form-row')) {

      // Find the target container from the hx-target attribute
      const targetSelector = triggerElement.getAttribute('hx-target');
      if (!targetSelector) return;

      const targetContainer = document.querySelector(targetSelector);
      if (!targetContainer) return;

      // Count how many form rows currently exist in the container
      const currentRowCount = targetContainer.querySelectorAll('.item-form-row').length;

      // Add the current count as the 'index' parameter for the GET request
      event.detail.parameters['index'] = currentRowCount;
   }
});


// --- LOGIC FOR REMOVING A FORM ---
document.body.addEventListener('click', function (event) {
   const removeButton = event.target.closest('.remove-form-row');
   if (!removeButton) return;

   event.preventDefault();

   const rowToRemove = removeButton.closest('.item-form-row');
   const container = rowToRemove.closest('tbody, div');

   // Count how many rows are currently VISIBLE
   const visibleRows = Array.from(container.querySelectorAll('.item-form-row'))
      .filter(row => row.style.display !== 'none');

   if (visibleRows.length <= 1) {
      alert('You cannot remove the last item. At least one item is required.');
      return;
   }

   const deleteCheckbox = rowToRemove.querySelector('input[name$="-DELETE"]');
   if (deleteCheckbox) {
      deleteCheckbox.checked = true;
      rowToRemove.style.display = 'none';
   } else {
      rowToRemove.remove();
      reindexFormsetRows(container);
   }
});


// --- UTILITY AND HELPER FUNCTIONS ---

// This function re-indexes all form rows after a *new* (unsaved) row is removed.
function reindexFormsetRows(container) {
   const formRows = container.querySelectorAll('.item-form-row');
   const totalFormsInput = document.querySelector('input[name$="-TOTAL_FORMS"]');

   if (!totalFormsInput) return;

   const prefix = totalFormsInput.name.replace('-TOTAL_FORMS', '');
   totalFormsInput.value = formRows.length;

   formRows.forEach((row, index) => {
      row.querySelectorAll('input, select, textarea').forEach(el => {
         const nameRegex = new RegExp(`^${prefix}-\\d+-`);
         const idRegex = new RegExp(`^id_${prefix}-\\d+-`);
         if (el.name && el.name.match(nameRegex)) {
            el.name = el.name.replace(nameRegex, `${prefix}-${index}-`);
         }
         if (el.id && el.id.match(idRegex)) {
            el.id = el.id.replace(idRegex, `id_${prefix}-${index}-`);
         }
      });
   });
}

// After ANY HTMX swap, update the TOTAL_FORMS count. This handles adding new rows.
document.body.addEventListener('htmx:afterSwap', function (event) {
   // Check if the swap happened inside a potential formset container
   const container = event.target;
   if (container.querySelectorAll('.item-form-row').length > 0) {
      const totalFormsInput = document.querySelector('input[name$="-TOTAL_FORMS"]');
      const formRows = container.querySelectorAll('.item-form-row');

      if (totalFormsInput) {
         totalFormsInput.value = formRows.length;
      }
   }
});