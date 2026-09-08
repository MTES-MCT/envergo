/**
 * Tracks clicks on elements with data-event-* attributes to Matomo.
 *
 * Exposes initAnalyticsTracking(container) so it can be called after
 * dynamic content insertion (e.g. htmx swaps).
 */
function initAnalyticsTracking(container) {
  container.querySelectorAll("[data-event-category]").forEach(function (el) {
    if (el._analyticsbound) return;
    el._analyticsbound = true;
    el.addEventListener("click", function () {
      var category = el.getAttribute("data-event-category");
      var action = el.getAttribute("data-event-action");
      var name = el.getAttribute("data-event-name");
      _paq.push(["trackEvent", category, action, name]);
    });
  });
}

window.addEventListener("load", function () {
  initAnalyticsTracking(document);
});
