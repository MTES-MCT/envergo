var _paq = window._paq || [];

window.addEventListener('load', function () {

  // Track click on links and buttons
  const links = document.querySelectorAll('[data-event-category]');
  links.forEach(link => link.addEventListener('click', function (evt) {
    const link = evt.currentTarget;
    const category = link.getAttribute('data-category');
    const action = link.getAttribute('data-action');
    const name = link.getAttribute('data-name');
    _paq.push(['trackEvent', category, action, name]);
  }));
});
