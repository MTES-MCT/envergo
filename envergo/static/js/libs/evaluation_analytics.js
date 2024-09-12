// Track a moulinette result page load
window.addEventListener('load', function () {
  _paq.push(['trackEvent', 'Evaluation', 'Visit', DEPARTMENT]);
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
      "request_reference": reference,
    }));
    fetch(url, { headers: headers, body: data, method: 'POST' });
  }));
});
