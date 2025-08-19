// /**
//  * Manages the state and behavior of the dynamic purchase order formset.
//  * @param {number} initialCount - The initial number of forms rendered by Django.
//  */
// export default function purchaseOrderForm(initialCount) {
//     return {
//         // --- STATE ---
//         totalForms: initialCount,
//         totalFormsInput: null, // A reference to the actual Django management form input

//         // --- LIFECYCLE HOOK ---
//         // The init() function is automatically run by Alpine when the component is initialized.
//         init() {
//             // Find the specific <input> that Django's management_form rendered.
//             // We look for it inside this component's root element ($el).
//             this.totalFormsInput = this.$el.querySelector('input[name=items-TOTAL_FORMS]');

//             // Use $watch to create a reactive link. Whenever the 'totalForms'
//             // variable changes, this function will run, keeping the real form input's
//             // value perfectly in sync.
//             this.$watch('totalForms', (newValue) => {
//                 if (this.totalFormsInput) {
//                     this.totalFormsInput.value = newValue;
//                 }
//             });

//             // Set the initial value on page load.
//             if (this.totalFormsInput) {
//                 this.totalFormsInput.value = this.totalForms;
//             }
//         },

//         // --- METHODS ---
//         /**
//          * Deletes a form row. It correctly handles both existing rows (with a DB record)
//          * and newly added rows (client-side only).
//          */
//         deleteRow(event) {
//             const row = event.target.closest('tr');
//             // Construct the ID of the DELETE checkbox based on the row's prefix ID
//             const deleteInput = document.getElementById('id_' + row.id + '-DELETE');

//             if (deleteInput) {
//                 // This is an EXISTING row that has a corresponding Django DELETE checkbox.
//                 // We check the box to mark it for deletion on the server and hide the row.
//                 deleteInput.checked = true;
//                 row.style.display = 'none';
//             } else {
//                 // This is a NEW row that was added dynamically.
//                 // It has no DELETE checkbox. We must remove it from the DOM
//                 // and decrement our client-side form count.
//                 row.remove();
//                 this.totalForms--;
//             }
//         }
//     }
// // }