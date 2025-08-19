// function updateFormCount() {
//    const totalFormsInput = document.querySelector('#id_item-TOTAL_FORMS');
//    const currentCount = parseInt(totalFormsInput.value);

//    // Update the HTMX request to include the current count
//    const button = event.target;
//    const currentUrl = button.getAttribute('hx-get');
//    button.setAttribute('hx-get', currentUrl + '?form_count=' + currentCount);

//    // Increment the total forms count after the request
//    setTimeout(() => {
//       totalFormsInput.value = currentCount + 1;
//    }, 100);
// }

// function deleteNewForm(button) {
//    // For new forms, just remove from DOM and update count
//    const row = button.closest('tr');
//    row.remove();

//    const totalFormsInput = document.querySelector('#id_item-TOTAL_FORMS');
//    totalFormsInput.value = parseInt(totalFormsInput.value) - 1;
// }

// function deleteExistingForm(button) {
//    // For existing forms, hide row and check DELETE checkbox
//    const row = button.closest('tr');
//    const deleteCheckbox = row.querySelector('input[name$="-DELETE"]');

//    if (deleteCheckbox) {
//       deleteCheckbox.checked = true;
//    }

//    row.style.display = 'none';
// }


// function updateFormCount() {
//    const totalFormsInput = document.querySelector('#id_item-TOTAL_FORMS');
//    const currentCount = parseInt(totalFormsInput.value);

//    // Update the HTMX request URL
//    const button = event.target;
//    button.setAttribute('hx-get', "{% url 'add_item_form' %}?item-TOTAL_FORMS=" + currentCount);
// }

// // Update form count after HTMX request completes
// document.addEventListener('htmx:afterSwap', function (event) {
//    if (event.target.id === 'items-container') {
//       const totalFormsInput = document.querySelector('#id_item-TOTAL_FORMS');
//       const currentCount = parseInt(totalFormsInput.value);
//       totalFormsInput.value = currentCount + 1;
//    }
// });

// function deleteNewForm(button) {
//    const row = button.closest('tr');
//    row.remove();

//    const totalFormsInput = document.querySelector('#id_item-TOTAL_FORMS');
//    totalFormsInput.value = parseInt(totalFormsInput.value) - 1;
// }

// function deleteExistingForm(button) {
//    const row = button.closest('tr');
//    const deleteCheckbox = row.querySelector('input[name$="-DELETE"]');

//    if (deleteCheckbox) {
//       deleteCheckbox.checked = true;
//    }

//    row.style.display = 'none';
// }

function updateFormCount() {
   const totalFormsInput = document.querySelector('#id_item-TOTAL_FORMS');
   const currentCount = parseInt(totalFormsInput.value);

   // Update the HTMX request URL with current form count
   const button = event.target;
   button.setAttribute('hx-get', "{% url 'add_item_form' %}?item-TOTAL_FORMS=" + currentCount);
}

// Update form count after HTMX request completes
document.addEventListener('htmx:afterSwap', function (event) {
   if (event.target.id === 'items-container') {
      const totalFormsInput = document.querySelector('#id_item-TOTAL_FORMS');
      const currentCount = parseInt(totalFormsInput.value);
      totalFormsInput.value = currentCount + 1;
   }
});

function deleteNewForm(button) {
   const row = button.closest('tr');
   row.remove();

   const totalFormsInput = document.querySelector('#id_item-TOTAL_FORMS');
   totalFormsInput.value = parseInt(totalFormsInput.value) - 1;
}

function deleteExistingForm(button) {
   const row = button.closest('tr');
   const deleteCheckbox = row.querySelector('input[name$="-DELETE"]');

   if (deleteCheckbox) {
      deleteCheckbox.checked = true;
   }

   row.style.display = 'none';
}