document.addEventListener('submit', function (event) {
  const form = event.target;
  const message = form.getAttribute('data-confirm');
  if (message && !window.confirm(message)) event.preventDefault();
});
// Hide flash messages after a short delay while keeping manual dismissal available.
window.setTimeout(() => {
  document.querySelectorAll('.alert').forEach((alert) => {
    if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(alert).close();
  });
}, 6500);
