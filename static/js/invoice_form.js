/**
 * Powers the Create Invoice page:
 *  - Toggles Registered vs Walk-in customer fields
 *  - Adds/removes product line item rows (Django management-form aware)
 *  - Auto-fills unit price when a product is selected from the catalog dropdown
 *  - Live-calculates line totals, subtotal, discount, tax, and grand total
 *    (client-side preview only — the backend re-validates everything on submit)
 */
document.addEventListener('DOMContentLoaded', function () {

  /* ---------------------------------------------------------------------
     1. Customer type toggle (Registered vs Walk-in)
  --------------------------------------------------------------------- */
  var customerTypeField = document.getElementById('id_customer_type');
  var registeredBlock = document.getElementById('registered-customer-block');
  var walkInBlock = document.getElementById('walkin-customer-block');

  function toggleCustomerBlocks() {
    if (!customerTypeField) return;
    var isRegistered = customerTypeField.value === 'REGISTERED';
    if (registeredBlock) registeredBlock.style.display = isRegistered ? '' : 'none';
    if (walkInBlock) walkInBlock.style.display = isRegistered ? 'none' : '';
  }

  if (customerTypeField) {
    customerTypeField.addEventListener('change', toggleCustomerBlocks);
    toggleCustomerBlocks();
  }

  /* ---------------------------------------------------------------------
     2. Dynamic invoice item rows
  --------------------------------------------------------------------- */
  var itemsTableBody = document.getElementById('invoice-items-body');
  var addItemBtn = document.getElementById('add-item-btn');
  var totalFormsInput = document.getElementById('id_items-TOTAL_FORMS');
  var emptyRowTemplate = document.getElementById('empty-item-row-template');

  function currentFormCount() {
    return parseInt(totalFormsInput.value, 10);
  }

  function addItemRow() {
    if (!emptyRowTemplate) return;
    var index = currentFormCount();
    var html = emptyRowTemplate.innerHTML.replace(/__prefix__/g, index);
    var tempWrapper = document.createElement('tbody');
    tempWrapper.innerHTML = html;
    var newRow = tempWrapper.firstElementChild;
    itemsTableBody.appendChild(newRow);
    totalFormsInput.value = index + 1;
    bindRowEvents(newRow);
  }

  function removeItemRow(row) {
    // If the row has a DELETE checkbox (existing form instance), tick it and hide.
    var deleteCheckbox = row.querySelector('input[name$="-DELETE"]');
    if (deleteCheckbox) {
      deleteCheckbox.checked = true;
      row.style.display = 'none';
    } else {
      row.remove();
    }
    recalculateTotals();
  }

  function bindRowEvents(row) {
    var productSelect = row.querySelector('.item-product-select');
    var priceInput = row.querySelector('.item-price-input');
    var qtyInput = row.querySelector('.item-qty-input');
    var removeBtn = row.querySelector('.remove-item-btn');

    if (productSelect) {
      productSelect.addEventListener('change', function () {
        var selectedOption = productSelect.options[productSelect.selectedIndex];
        var price = selectedOption.getAttribute('data-price');
        var stock = selectedOption.getAttribute('data-stock');
        var nameInput = row.querySelector('.item-name-input');

        if (price && priceInput) {
          priceInput.value = price;
          priceInput.readOnly = true; // catalog price is locked; blank product = manual entry
        }
        if (nameInput) nameInput.value = '';
        if (stock) {
          var stockHint = row.querySelector('.stock-hint');
          if (stockHint) stockHint.textContent = 'Available: ' + stock;
        }
        recalculateTotals();
      });
    }

    if (priceInput) priceInput.addEventListener('input', recalculateTotals);
    if (qtyInput) qtyInput.addEventListener('input', recalculateTotals);
    if (removeBtn) removeBtn.addEventListener('click', function () { removeItemRow(row); });
  }

  if (addItemBtn) {
    addItemBtn.addEventListener('click', addItemRow);
  }

  document.querySelectorAll('#invoice-items-body tr').forEach(bindRowEvents);

  /* ---------------------------------------------------------------------
     3. Live totals calculation (subtotal, discount, tax, grand total)
        Mirrors invoices.services.recalculate_invoice_totals() logic for
        an instant preview. The backend remains the source of truth.
  --------------------------------------------------------------------- */
  var subtotalDisplay = document.getElementById('subtotal-display');
  var discountAmountDisplay = document.getElementById('discount-amount-display');
  var taxAmountDisplay = document.getElementById('tax-amount-display');
  var grandTotalDisplay = document.getElementById('grand-total-display');

  var discountTypeField = document.getElementById('id_discount_type');
  var discountValueField = document.getElementById('id_discount_value');
  var taxPercentageField = document.getElementById('id_tax_percentage');

  function round2(value) {
    return Math.round((value + Number.EPSILON) * 100) / 100;
  }

  function recalculateTotals() {
    var subtotal = 0;

    document.querySelectorAll('#invoice-items-body tr').forEach(function (row) {
      if (row.style.display === 'none') return; // deleted rows
      var priceInput = row.querySelector('.item-price-input');
      var qtyInput = row.querySelector('.item-qty-input');
      var lineTotalDisplay = row.querySelector('.item-line-total');

      var price = priceInput ? parseFloat(priceInput.value) || 0 : 0;
      var qty = qtyInput ? parseFloat(qtyInput.value) || 0 : 0;
      var lineTotal = round2(price * qty);

      if (lineTotalDisplay) lineTotalDisplay.textContent = lineTotal.toFixed(2);
      subtotal += lineTotal;
    });
    subtotal = round2(subtotal);

    var discountType = discountTypeField ? discountTypeField.value : 'NONE';
    var discountValue = discountValueField ? parseFloat(discountValueField.value) || 0 : 0;
    var discountAmount = 0;

    if (discountType === 'PERCENTAGE') {
      discountAmount = round2(subtotal * (discountValue / 100));
    } else if (discountType === 'FIXED') {
      discountAmount = round2(Math.min(discountValue, subtotal));
    }

    var taxable = subtotal - discountAmount;
    var taxPercentage = taxPercentageField ? parseFloat(taxPercentageField.value) || 0 : 0;
    var taxAmount = round2(taxable * (taxPercentage / 100));
    var grandTotal = round2(taxable + taxAmount);

    if (subtotalDisplay) subtotalDisplay.textContent = subtotal.toFixed(2);
    if (discountAmountDisplay) discountAmountDisplay.textContent = discountAmount.toFixed(2);
    if (taxAmountDisplay) taxAmountDisplay.textContent = taxAmount.toFixed(2);
    if (grandTotalDisplay) grandTotalDisplay.textContent = grandTotal.toFixed(2);
  }

  if (discountTypeField) discountTypeField.addEventListener('change', recalculateTotals);
  if (discountValueField) discountValueField.addEventListener('input', recalculateTotals);
  if (taxPercentageField) taxPercentageField.addEventListener('input', recalculateTotals);

  recalculateTotals();

  /* ---------------------------------------------------------------------
     4. Quick "walk-in vs registered" customer search (optional AJAX hook)
        Uses customers:api_customer_search — wire a <select> with
        id="id_customer" + a search box with id="customer-search-input"
        if you want live filtering beyond the plain <select>.
  --------------------------------------------------------------------- */
  var customerSearchInput = document.getElementById('customer-search-input');
  if (customerSearchInput) {
    var searchTimeout = null;
    customerSearchInput.addEventListener('input', function () {
      clearTimeout(searchTimeout);
      var query = customerSearchInput.value.trim();
      searchTimeout = setTimeout(function () {
        if (query.length < 2) return;
        fetch('/customers/api/search/?q=' + encodeURIComponent(query))
          .then(function (res) { return res.json(); })
          .then(function (data) {
            var select = document.getElementById('id_customer');
            if (!select) return;
            select.innerHTML = '<option value="">---------</option>';
            data.results.forEach(function (customer) {
              var opt = document.createElement('option');
              opt.value = customer.id;
              opt.textContent = customer.text + (customer.phone ? ' (' + customer.phone + ')' : '');
              select.appendChild(opt);
            });
          });
      }, 300);
    });
  }
});
