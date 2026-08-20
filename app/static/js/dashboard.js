document.addEventListener('DOMContentLoaded', function () {
  // Template card selection highlight
  document.querySelectorAll('.template-select-card input[type="radio"]').forEach(function (radio) {
    radio.addEventListener('change', function () {
      document.querySelectorAll('.template-select-card').forEach(function (card) {
        card.classList.remove('selected');
      });
      if (radio.checked) {
        radio.closest('.template-select-card').classList.add('selected');
      }
    });
  });

  // Disable the submit button and show a spinner on every plain form POST, so a slow
  // action (PSD/CMYK generation) can't be fired twice by an impatient double-click, and
  // the user gets some feedback instead of a frozen-looking page.
  document.querySelectorAll('form:not([method="GET" i])').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      var btn = form.querySelector('button[type="submit"], button:not([type])');
      if (!btn || btn.disabled) return;
      if (form.hasAttribute('data-no-spinner')) return;
      btn.dataset.originalHtml = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> '
        + (btn.dataset.loadingText || 'Processando...');
    });
  });
});
