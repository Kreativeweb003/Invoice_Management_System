document.addEventListener('DOMContentLoaded', function () {
  // Mobile sidebar toggle
  var toggleBtn = document.querySelector('.navbar-toggle');
  var sidebar = document.querySelector('.sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('open');
    });
  }

  // Dismissible alerts
  document.querySelectorAll('.alert-close').forEach(function (btn) {
    btn.addEventListener('click', function () {
      btn.closest('.alert').remove();
    });
  });

  // Auto-dismiss success alerts after 5s
  document.querySelectorAll('.alert-success').forEach(function (alert) {
    setTimeout(function () { alert.style.display = 'none'; }, 5000);
  });

  // Generic confirm-before-submit for any form with data-confirm="message"
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (!confirm(form.getAttribute('data-confirm'))) {
        e.preventDefault();
      }
    });
  });
});
