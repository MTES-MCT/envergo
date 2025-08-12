// Track when a PJ link is clicked
window.addEventListener('load', function () {
  const pjLinks = document.querySelectorAll('.ds-message__pj');
  pjLinks.forEach(btn => btn.addEventListener('click', function (evt) {

    // Delay the click event so we have time to track the click event
    // It's ugly but… ¯\_(ツ)_/¯
    evt.preventDefault();
    const link = evt.currentTarget;
    setTimeout(function () { window.location = link.href }, 350);

    // Log the event
    const reference = link.getAttribute('data-reference');
    let url = EVENTS_URL;
    let token = CSRF_TOKEN;
    let headers = { "X-CSRFToken": token };
    let data = new FormData();
    data.append("category", "messagerie");
    data.append("action", "lecture_pj");
    fetch(url, { headers: headers, body: data, method: 'POST' });
  }));
});
