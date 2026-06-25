'use strict';

/* ═══════════════════════════════════════════════════════════════════════════════
   app.js — Global frontend behaviours for RetailMS
   ═══════════════════════════════════════════════════════════════════════════════

   Sections:
   1. Modal management                 (all pages with #modal_container)
   2. SweetAlert2 toast system         (all pages — via HX-Trigger / DOMContentLoaded)
   3. CFA Agreement live preview       (templates/customers/modals/cfa_agreement_modal.html)
   4. Sidebar active nav link          (all pages)
   5. Barcode scanner auto-advance     (templates/inventory/transformation_form.html)
   6. Select2 initialisation           (templates/customers/sales/normal_sale_form.html)
   7. Purchase Agreement totals        (templates/customers/purchase_agreement_form.html)
   ═══════════════════════════════════════════════════════════════════════════════ */


// ═══════════════════════════════════════════════════════════════════════════════
// 1. Modal management
//    Works for: every page that loads a modal into #modal_container via HTMX.
//    Canonical reference: modal_deposit view + deposit_modal.html
// ═══════════════════════════════════════════════════════════════════════════════

function closeModal() {
  document.getElementById("modal_container").innerHTML = "";
}

// Event delegation for modal close triggers — works even after HTMX re-renders
document.getElementById("modal_container").addEventListener("click", function (e) {
  if (e.target.id === "modal-backdrop") {
    closeModal();
    return;
  }
  if (e.target.closest("#modal-close-btn")) {
    closeModal();
    return;
  }
  if (e.target.closest("#modal-cancel-btn")) {
    closeModal();
  }
});

// Hide modal: fires before HTMX swaps a 204/empty response targeting #modal-dialog
htmx.on("htmx:beforeSwap", function (e) {
  if (e.detail.target.id === "modal-dialog" && !e.detail.xhr.response) {
    closeModal();
    e.detail.shouldSwap = false;
  }
});

// Escape key closes modal
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") closeModal();
});

// Mobile sidebar: toggle open/close
function closeMobileSidebar() {
  var sidebar = document.getElementById("sidebar");
  var overlay = document.getElementById("sidebar-overlay");
  if (sidebar) sidebar.classList.remove("open");
  if (overlay) overlay.classList.remove("open");
}

function isMobile() {
  return window.innerWidth < 1024;
}

// Hamburger toggle
document.addEventListener("DOMContentLoaded", function () {
  var toggleBtn = document.getElementById("mobile-menu-toggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", function () {
      var sidebar = document.getElementById("sidebar");
      var overlay = document.getElementById("sidebar-overlay");
      if (sidebar) sidebar.classList.toggle("open");
      if (overlay) overlay.classList.toggle("open");
    });
  }

  // Overlay click closes sidebar
  var overlay = document.getElementById("sidebar-overlay");
  if (overlay) {
    overlay.addEventListener("click", function () {
      closeMobileSidebar();
    });
  }

  // Sidebar link clicks close mobile sidebar
  var sidebar = document.getElementById("sidebar");
  if (sidebar) {
    sidebar.addEventListener("click", function (e) {
      var link = e.target.closest("a.nav-link");
      if (link && isMobile()) {
        closeMobileSidebar();
      }
    });
  }
});


// ═══════════════════════════════════════════════════════════════════════════════
// 2. SweetAlert2 toast system
//    Works for: all pages.  Messages arrive via HtmxMessageMiddleware (HX-Trigger
//    header) on HTMX responses, or are rendered inline in index.html on full loads.
// ═══════════════════════════════════════════════════════════════════════════════

document.addEventListener("messages", function (e) {
  var msgs = Array.isArray(e.detail) ? e.detail : e.detail && e.detail.value;
  if (!msgs || msgs.length === 0) return;
  var queue = Promise.resolve();
  msgs.forEach(function (msg) {
    queue = queue.then(function () {
      return Swal.fire(buildSwalConfig(msg));
    });
  });
});

function buildSwalConfig(msg) {
  var tag = (msg.tags || "info").split(" ").pop();
  var iconMap = { debug: "info", info: "info", success: "success", warning: "warning", error: "error" };
  var icon = iconMap[tag] || "info";
  var isError = icon === "error";
  return {
    text:              msg.message,
    icon:              icon,
    toast:             true,
    position:          "top-end",
    showConfirmButton: false,
    timer:             isError ? 0 : 4000,
    timerProgressBar:  !isError,
    showCloseButton:   true,
    customClass:       { popup: "swal-rms-popup" },
    didOpen: function (popup) {
      popup.addEventListener("mouseenter", Swal.stopTimer);
      popup.addEventListener("mouseleave", Swal.resumeTimer);
    },
  };
}


// ═══════════════════════════════════════════════════════════════════════════════
// 3. CFA Agreement live preview
//    Works for: templates/customers/modals/cfa_agreement_modal.html
//    Updates XOF / Naira previews in real time as the user types.
// ═══════════════════════════════════════════════════════════════════════════════

function updateCfaPreview(amountInput, rateInput) {
  const amt  = parseFloat(amountInput.value) || 0;
  const rate = parseFloat(rateInput.value)   || 0;
  const xof  = rate > 0 ? Math.round((amt / rate) * 1000 / 100) * 100 : 0;

  const set = function(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  set('cfa-xof-preview',   xof.toLocaleString() + ' XOF');
  set('cfa-naira-preview',  '₦' + amt.toLocaleString());
  set('cfa-rate-preview',   '₦' + rate.toLocaleString() + ' / 1,000 XOF');

  const available = parseFloat(
    document.getElementById('cfa-available-balance')?.dataset.value || '0'
  );
  const warn = document.getElementById('cfa-balance-warn');
  if (warn) warn.classList.toggle('hidden', amt <= available || amt === 0);
}


// ═══════════════════════════════════════════════════════════════════════════════
// 4. Sidebar active nav link
//    Works for: all pages. Highlights the correct sidebar item after HTMX swaps
//    and on full page loads.
// ═══════════════════════════════════════════════════════════════════════════════

function updateActiveNav() {
  const path = window.location.pathname;
  const links = Array.from(document.querySelectorAll('#sidebar .nav-link'));

  links.forEach(function(link) {
    link.classList.remove('active');
  });

  const realLinks = links
    .filter(function(link) {
      const href = link.getAttribute('href') || '';
      return href && href !== '#';
    })
    .sort(function(a, b) {
      return (b.getAttribute('href') || '').length - (a.getAttribute('href') || '').length;
    });

  for (let i = 0; i < realLinks.length; i++) {
    const link = realLinks[i];
    const href = link.getAttribute('href') || '';
    if (href === '/' ? path === '/' : path.startsWith(href)) {
      link.classList.add('active');
      break;
    }
  }
}

document.addEventListener('htmx:afterSettle', function() {
  setTimeout(updateActiveNav, 10);
});
document.addEventListener('DOMContentLoaded', updateActiveNav);


// ═══════════════════════════════════════════════════════════════════════════════
// 5. Barcode scanner: auto-advance engine → chassis field
//    Works for: templates/inventory/transformation_form.html
// ═══════════════════════════════════════════════════════════════════════════════

document.addEventListener('input', function(e) {
  if (e.target.classList.contains('scan-field-engine') && e.target.value.length >= 8) {
    const row = e.target.closest('.formset-row');
    if (row) {
      const next = row.querySelector('.scan-field-chassis');
      if (next) next.focus();
    }
  }
});


// ═══════════════════════════════════════════════════════════════════════════════
// 6. Select2 initialisation
//    Works for: templates/customers/sales/normal_sale_form.html
//    Customer dropdown + boxed product dropdowns + serialized item dropdowns.
//
//    FIX: dropdownParent for .select2-customer is set to $('body') instead of
//    $('#customer-select-wrapper').  This prevents Select2's generated
//    .select2-container from living inside the HTMX swap target, which caused
//    a double-render (raw <select> + orphaned Select2 UI) after every
//    customerCreated swap.  The beforeSwap handler also explicitly removes any
//    stray .select2-container siblings when #customer-select-wrapper is the
//    swap target.
// ═══════════════════════════════════════════════════════════════════════════════

function initCustomerSelect2() {
  $('.select2-customer').each(function() {
    const $select = $(this);
    if ($select.data('select2')) return; // already initialized — skip

    const isModal = $select.closest('#modal-dialog').length > 0;
    const config = {
      placeholder: $select.data('placeholder') || 'Select a customer',
      allowClear: false,
      width: '100%',
      templateResult: function(data) {
        if (!data.id) return data.text;
        const balance = $(data.element).data('balance');
        if (balance === undefined) return data.text;
        return $('<span>').text(data.text).append(
          $('<small>').addClass('block text-slate-400').text(
            'Available: ₦' + parseFloat(balance).toLocaleString('en-NG', {
              minimumFractionDigits: 0,
              maximumFractionDigits: 0
            })
          )
        );
      },
      templateSelection: function(data) {
        const text = data.text;
        return text.includes(' — ') ? text.split(' — ')[0] : text;
      }
    };

    // FIX: Use $('body') as dropdownParent for the normal-sale customer select
    // so Select2's generated container lives OUTSIDE #customer-select-wrapper.
    // Putting it inside the swap target was the cause of the double-render bug.
    if (!isModal && $select.closest('#customer-select-wrapper').length) {
      config.dropdownParent = $('body');
    } else if (isModal) {
      config.dropdownParent = $select.closest('#modal-dialog');
    }

    $select.select2(config);

    // Only attach summary handler for the normal-sale-form customer select
    if ($select.attr('id') === 'id_customer') {
      $select.on('select2:select', function(e) {
        const option = e.params.data.element;
        const balance = parseFloat($(option).data('balance') || 0);
        const name = e.params.data.text.split(' — ')[0];

        const summary = document.getElementById('customer-summary');
        if (summary) summary.classList.remove('hidden');
        const nameEl = document.getElementById('customer-name');
        if (nameEl) nameEl.textContent = name;
        const balEl = document.getElementById('customer-balance');
        if (balEl) {
          balEl.textContent = '₦' + balance.toLocaleString('en-NG', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
          });
        }
      });

      const selected = $select.find(':selected');
      if (selected.length && selected.val()) {
        $select.trigger({
          type: 'select2:select',
          params: { data: { id: selected.val(), text: selected.text(), element: selected[0] } }
        });
      }
    }
  });
}

function initBoxedSelect2() {
  $('.select2-product').each(function() {
    const $sel = $(this);
    if ($sel.data('select2')) return; // already initialized — skip
    const $row = $sel.closest('.item-form-row');
    const isModal = $sel.closest('#modal-dialog').length > 0;
    const config = {
      placeholder: $sel.data('placeholder') || 'Select a product',
      allowClear: false,
      width: '100%'
    };
    if (isModal) {
      config.dropdownParent = $sel.closest('#modal-dialog');
    } else if ($row.length) {
      // FIX: Use body for formset rows instead of the individual row.
      // Setting dropdownParent to $row caused the browser to forcibly
      // scroll back to the focused search field inside the row, and
      // dropdowns that open then immediately close because the row
      // element clips / misroutes click events.
      config.dropdownParent = $('body');
    }
    $sel.select2(config);
  });
}

function initSelect2Enabled() {
  $('.select2-enabled').each(function() {
    const $sel = $(this);
    if ($sel.data('select2')) return; // already initialized — skip
    const isModal = $sel.closest('#modal-dialog').length > 0;
    const config = {
      placeholder: $sel.data('placeholder') || 'Select an option',
      allowClear: false,
      width: '100%'
    };
    if (isModal) {
      config.dropdownParent = $sel.closest('#modal-dialog');
    }
    $sel.select2(config);
  });
}

function initCoupledSelect2() {
  // Single-select serial pickers
  $('.select2-serial, .select2-serial-item').each(function() {
    const $sel = $(this);
    if ($sel.data('select2')) return; // already initialized — skip
    const placeholder = $sel.data('placeholder') || 'Select a serial item';
    const isModal = $sel.closest('#modal-dialog').length > 0;
    const config = {
      placeholder: placeholder,
      allowClear: false,
      width: '100%'
    };
    if (isModal) {
      config.dropdownParent = $sel.closest('#modal-dialog');
    } else {
      config.dropdownParent = $('body');
    }
    $sel.select2(config);
  });

  // Multi-select serial pickers (agreement fulfillment)
  $('.select2-multi-serial').each(function() {
    const $sel = $(this);
    if ($sel.data('select2')) return; // already initialized — skip
    const placeholder = $sel.data('placeholder') || 'Select serialized units';
    const isModal = $sel.closest('#modal-dialog').length > 0;
    const config = {
      placeholder: placeholder,
      allowClear: true,
      width: '100%',
      closeOnSelect: false,
      templateResult: function(data) {
        if (!data.id) return data.text;
        return $('<span>').text(data.text);
      },
      templateSelection: function(data) {
        if (!data.id) return data.text;
        // Item numbers never contain spaces — take the first word.
        // The option text is "ITEM-XXXX — ENG: ... — CHA: ...".
        return data.text.split(/\s/)[0] || data.text;
      }
    };
    if (isModal) {
      config.dropdownParent = $sel.closest('#modal-dialog');
    } else {
      config.dropdownParent = $('body');
    }
    $sel.select2(config);
  });
}

function initAllSelect2() {
  // Guard: jQuery and Select2 must be available.
  if (typeof $ === 'undefined' || !$.fn || !$.fn.select2) {
    console.warn('[app.js] Select2 not available yet, skipping init');
    return;
  }
  try {
    initCustomerSelect2();
    initBoxedSelect2();
    initCoupledSelect2();
    initSelect2Enabled();
  } catch (err) {
    console.error('[app.js] Select2 init error:', err);
  }
}

// Helper: schedule init on the next animation frame so the browser has
// finished laying out the newly swapped DOM before Select2 measures
// elements and builds its dropdown container.
function scheduleInitSelect2() {
  if (window.__select2InitScheduled) return;
  window.__select2InitScheduled = true;
  requestAnimationFrame(function() {
    window.__select2InitScheduled = false;
    initAllSelect2();
  });
}

// Initialize on full page load
document.addEventListener('DOMContentLoaded', initAllSelect2);

// Re-initialize after HTMX swaps.  We listen on BOTH afterSwap and
// afterSettle because different swap types (partial vs boosted) can fire
// them at slightly different times.  requestAnimationFrame deduplicates.
document.addEventListener('htmx:afterSwap', function() {
  scheduleInitSelect2();
});
document.addEventListener('htmx:afterSettle', function() {
  scheduleInitSelect2();
});

// Before HTMX swaps content:
//  1. Destroy Select2 instances inside the target to prevent ghost event
//     listeners on the document that would break search on newly swapped selects.
//  2. FIX: If the swap target is #customer-select-wrapper (outerHTML swap
//     triggered by customerCreated), also remove any stray .select2-container
//     elements that Select2 appended as siblings inside the wrapper previously.
//     With dropdownParent now set to $('body') going forward, this cleanup
//     handles any containers created before this fix was applied.
document.addEventListener('htmx:beforeSwap', function(e) {
  const target = e.detail.target;
  if (!target) return;

  // Destroy all Select2 instances inside the swap target
  $(target).find('select').addBack('select').each(function() {
    const $sel = $(this);
    if ($sel.data('select2')) {
      $sel.select2('destroy');
    }
  });

  // FIX: Remove any orphaned Select2 containers that are siblings of
  // #customer-select-wrapper — these are leftovers from when dropdownParent
  // was set to the wrapper itself, causing the double-render.
  if (target.id === 'customer-select-wrapper') {
    $(target).siblings('.select2-container').remove();
  }
});


// ═══════════════════════════════════════════════════════════════════════════════
// 7. Purchase Agreement totals
//    Works for: templates/customers/purchase_agreement_form.html
//    Live-calculates agreement total and remaining balance as rows are added
//    or edited.
// ═══════════════════════════════════════════════════════════════════════════════

function updateAgreementTotal() {
  let total = 0;
  document.querySelectorAll('.item-form-row').forEach(function (row) {
    const deleteInput = row.querySelector('input[name$="-DELETE"]');
    if (deleteInput && deleteInput.checked) return;

    const qty = parseFloat(
      row.querySelector('input[name$="-quantity_ordered"]')?.value
    ) || 0;
    const price = parseFloat(
      row.querySelector('input[name$="-price_per_unit"]')?.value
    ) || 0;
    total += qty * price;
  });

  const totalEl = document.getElementById('agreement-total');
  if (totalEl) {
    totalEl.textContent = '₦' + total.toLocaleString('en-NG', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  }

  const balanceAfterEl = document.getElementById('balance-after');
  const availableEl = document.getElementById('balance-after-row');
  if (balanceAfterEl && availableEl) {
    const available = parseFloat(availableEl.dataset.available || '0');
    const remaining = available - total;
    balanceAfterEl.textContent = '₦' + remaining.toLocaleString('en-NG', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
    balanceAfterEl.classList.toggle('text-rose-600', remaining < 0);
    balanceAfterEl.classList.toggle('text-slate-800', remaining >= 0);
  }
}

// Recalculate when user types in quantity or price fields
document.addEventListener('input', function (e) {
  if (
    e.target.name?.endsWith('-quantity_ordered') ||
    e.target.name?.endsWith('-price_per_unit')
  ) {
    updateAgreementTotal();
  }
});

// Recalculate after HTMX swaps in the formset container (add/remove row)
document.addEventListener('htmx:afterSwap', function (e) {
  if (e.detail.target?.id === 'formset-container') {
    updateAgreementTotal();
  }
});

document.addEventListener('DOMContentLoaded', updateAgreementTotal);