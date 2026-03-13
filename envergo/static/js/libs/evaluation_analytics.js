// Track an AR page load
window.addEventListener('load', function () {
  _paq.push(['trackEvent', 'Evaluation', 'Visit', DEPARTMENT]);
});

// Track when an appointment request button is clicked
window.addEventListener("load", function () {
  const pickAppointmentBtn = document.getElementById("pick-appointment-btn");
  if (!pickAppointmentBtn) {
    return;
  }
  pickAppointmentBtn.addEventListener("click", function (evt) {
    _paq.push(["trackEvent", "Evaluation", "ChooseAppointmentClick"]);
  });
});

// Track when a "self declaration" button is clicked
window.addEventListener('load', function () {
  const ctaButtons = document.querySelectorAll('.self-declaration-cta');
  ctaButtons.forEach(btn => btn.addEventListener('click', function (evt) {

    evt.preventDefault();
    const btn = evt.currentTarget;

    // Log the event, then navigate once the request completes (or fails)
    let url = EVENTS_URL;
    let token = CSRF_TOKEN;
    let headers = { "X-CSRFToken": token };
    let data = new FormData();
    data.append("category", "compliance");
    data.append("action", "page-click");
    data.append("metadata", btn.getAttribute("data-sql-event-metadata"));
    fetch(url, { headers: headers, body: data, method: 'POST' })
      .finally(function () { window.location = btn.href; });
  }));
});

// Dismiss the self declaration block for 48 hours
window.addEventListener('load', function () {
  const key = "self-declaration-cta-dismissed";
  const el = document.getElementById("self-declaration-cta-v2");
  if(!el){
    return
  }
  const dismissed = localStorage.getItem(key);
  if (dismissed && Date.now() - parseInt(dismissed) < 48 * 3600 * 1000) {
    el.style.display = "none";
  }
  document
    .getElementById("self-declaration-cta-close-btn")
    .addEventListener("click", function () {
      el.style.display = "none";
      localStorage.setItem(key, Date.now().toString());

      _paq.push(["trackEvent", "Evaluation", "HideSelfDeclareClick"]);
    });
});
