var _paq = window._paq || [];

// Track an event when a regulation main "read more" btn is clicked
window.addEventListener('load', function () {
  const showMoreBtns = document.querySelectorAll('.read-more-btn');
  showMoreBtns.forEach(btn => btn.addEventListener('click', function (evt) {
    const btn = evt.currentTarget;
    const target = btn.getAttribute('aria-controls');
    const expanded = btn.getAttribute('aria-expanded');
    const action = expanded == 'false' ? 'Expand' : 'Conceal';
    _paq.push(['trackEvent', 'Content', action, target]);
  }));
});

// Track a moulinette result page load
window.addEventListener('load', function () {
  _paq.push(['trackEvent', 'Simulation', 'Result', DEPARTMENT]);
});

// Track when a summary link is clicked
window.addEventListener('load', function () {
  const summaryLinks = document.querySelectorAll('.summary-link');
  summaryLinks.forEach(link => link.addEventListener('click', function (evt) {
    // Log the event
    const link = evt.currentTarget;
    const title = link.getAttribute('data-regulation');
    _paq.push(['trackEvent', 'Content', 'JumpToAnchor', title]);
  }));
});


// Track when a "self declaration" button is clicked
window.addEventListener('load', function () {
  const ctaButtons = document.querySelectorAll('.self-declaration-cta');
  ctaButtons.forEach(btn => btn.addEventListener('click', function (evt) {

    // Delay the click event so we have time to track the click event
    // It's ugly but… ¯\_(ツ)_/¯
    evt.preventDefault();
    const btn = evt.currentTarget;
    setTimeout(function () { window.location = btn.href }, 350);

    // Log the event
    const reference = btn.getAttribute('data-reference');
    let url = EVENTS_URL;
    let token = CSRF_TOKEN;
    let headers = { "X-CSRFToken": token };
    let data = new FormData();
    data.append("category", "compliance");
    data.append("action", "page-click");
    data.append("metadata", JSON.stringify({
      "reference": reference,
    }));
    fetch(url, { headers: headers, body: data, method: 'POST' });
  }));
});
