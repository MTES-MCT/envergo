window.addEventListener('load', function () {
  // Track click on links and buttons
  const links = document.querySelectorAll('[data-event-category]');
  links.forEach(link => link.addEventListener('click', function (evt) {
    const link = evt.currentTarget;
    const category = link.getAttribute('data-event-category');
    const action = link.getAttribute('data-event-action');
    const name = link.getAttribute('data-event-name');
    _paq.push(['trackEvent', category, action, name]);
  }));
});
