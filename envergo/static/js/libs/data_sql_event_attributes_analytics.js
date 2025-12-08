window.addEventListener('load', function () {
  // Track click on links and buttons
  const links = document.querySelectorAll('[data-sql-event-category]');
  links.forEach(link => link.addEventListener('click', function (evt) {
    // Block the navigation for sending an analytics event before
    evt.preventDefault();
    const category = link.getAttribute('data-sql-event-category');
    const action = link.getAttribute('data-sql-event-action');
    const metadata = link.getAttribute('data-sql-event-metadata');
    let url = EVENTS_URL;
    let token = CSRF_TOKEN;
    let headers = {"X-CSRFToken": token};
    let data = new FormData();
    data.append("category", category);
    data.append("action", action);
    data.append("metadata", metadata);
    fetch(url, {
      headers: headers, body: data, method: 'POST'
    }).catch(error => {
      console.warn('Tracking failed:', error);
      // We still want to navigate even on failure
    }).finally(() => {
      // Proceed with navigation manually
      window.open(link.href, link.target);
    });
  }));
});
