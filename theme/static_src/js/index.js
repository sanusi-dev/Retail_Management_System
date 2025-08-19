// theme/static_src/js/index.js

import Alpine from 'alpinejs';
import persist from '@alpinejs/persist';

// --- IMPORT YOUR COMPONENT FROM ITS SEPARATE FILE ---
// import purchaseOrderForm from './components/purchaseOrderForm';

// --- CONFIGURATION ---
Alpine.plugin(persist);

// --- REGISTER YOUR ALPINE COMPONENTS ---
// This tells Alpine: when you see x-data="purchaseOrderForm", use the function we imported.
// Alpine.data('purchaseOrderForm', purchaseOrderForm);

// Make Alpine available globally for debugging
window.Alpine = Alpine;

// --- START ---
Alpine.start();
console.log("Alpine.js initialized and started locally.");