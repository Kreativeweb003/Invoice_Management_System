/**
 * Chart.js wiring. Each function is defensive (checks the canvas exists)
 * so this single file can be included on any page without errors, and
 * reads its data from a JSON <script type="application/json"> block
 * rendered server-side, OR fetches from the reports API endpoints.
 *
 * Requires Chart.js to be loaded before this file, e.g.:
 * <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
 */

function initSalesTrendChart(canvasId, labels, salesData) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;

  new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Sales',
        data: salesData,
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37, 99, 235, 0.08)',
        tension: 0.3,
        fill: true,
        pointRadius: 3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { callback: function (v) { return v; } } }
      }
    }
  });
}

function initStatusBreakdownChart(canvasId, labels, counts, colors) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;

  new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: counts,
        backgroundColor: colors || ['#d97706', '#0891b2', '#16a34a', '#dc2626', '#9ca3af'],
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function initPaymentMethodChart(canvasId, labels, amounts) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;

  new Chart(canvas, {
    type: 'pie',
    data: {
      labels: labels,
      datasets: [{
        data: amounts,
        backgroundColor: ['#2563eb', '#16a34a', '#d97706', '#0891b2', '#dc2626', '#9ca3af'],
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } }
    }
  });
}

function initAgingBucketsChart(canvasId, labels, totals) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;

  new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Outstanding Amount',
        data: totals,
        backgroundColor: '#dc2626',
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } }
    }
  });
}

/**
 * Fetches a report trend endpoint (sales or payments) and renders it into
 * a line chart. Used when the report page wants to refresh the chart via
 * AJAX after the user changes the date filter, instead of reloading.
 */
function refreshTrendChartFromAPI(apiUrl, chartInstance, canvasId) {
  fetch(apiUrl)
    .then(function (res) { return res.json(); })
    .then(function (data) {
      if (chartInstance) {
        chartInstance.data.labels = data.labels;
        chartInstance.data.datasets[0].data = data.sales || data.collected;
        chartInstance.update();
      }
    });
}
