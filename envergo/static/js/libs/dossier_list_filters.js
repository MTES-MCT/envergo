/**
 * Dynamic filtering on the dossier list page.
 *
 * Provides immediate visual feedback (loading indicator) on filter
 * interactions, resets form controls on the reset button click, and
 * re-initializes dynamic elements after htmx content swaps.
 */
(function () {
  "use strict";

  // Make table rows navigable by click, targeting the first link in each row.
  function initRowClick(container) {
    container.querySelectorAll("#table-dossier-list tbody tr").forEach(function (row) {
      if (row._rowClickBound) return;
      row._rowClickBound = true;

      var link = row.querySelector("td:first-child a");
      if (!link) return;

      row.addEventListener("click", function (e) {
        if (e.target.closest("a, button, input, textarea, select")) return;
        window.location.href = link.href;
      });
      row.style.cursor = "pointer";
    });
  }

  // Replace the results area with a spinner, called before htmx's debounced request.
  function showLoadingIndicator() {
    var target = document.getElementById("dossier-results");
    if (!target) return;
    target.innerHTML =
      '<div class="fr-my-4w" style="text-align: center;">' +
      '<span class="fr-icon-refresh-line icon-spinner"></span> ' +
      'Chargement en cours…' +
      '</div>';
  }

  // Set all filter controls back to their default state (all categories, no follow filter, closed hidden).
  function resetFormToDefaults() {
    var form = document.getElementById("dossier-filter-form");
    if (!form) return;
    document.getElementById("followed-by-off").checked = true;
    document.getElementById("show-closed-dossiers").checked = false;
    form.querySelectorAll('input[name="category"]').forEach(function (cb) {
      cb.checked = true;
    });
  }

  var CATEGORY_NAMES = { "ru": "Ru", "l350_3": "Aa", "hru": "Hru" };

  // Track checkbox filter interactions to Matomo with on/off state in the event name.
  function trackCheckboxEvent(checkbox, action, baseName) {
    var suffix = checkbox.checked ? "On" : "Off";
    _paq.push(["trackEvent", "ProjectList", action, baseName + suffix]);
  }

  // Align filter controls with the current URL params, used after browser back/forward.
  function syncFormFromUrl() {
    var params = new URLSearchParams(window.location.search);
    var form = document.getElementById("dossier-filter-form");
    if (!form) return;

    var followedBy = params.get("followed_by") || "off";
    form.querySelectorAll('input[name="followed_by"]').forEach(function (r) {
      r.checked = (r.value === followedBy);
    });

    var showClosed = form.querySelector("#show-closed-dossiers");
    if (showClosed) {
      showClosed.checked = params.has("show_closed");
    }

    var selectedCats = params.getAll("category");
    form.querySelectorAll('input[name="category"]').forEach(function (cb) {
      cb.checked = selectedCats.length === 0 || selectedCats.includes(cb.value);
    });
  }

  window.addEventListener("load", function () {
    initRowClick(document);

    var form = document.getElementById("dossier-filter-form");
    if (form) {
      form.addEventListener("change", function (e) {
        var input = e.target;
        if (input.name === "show_closed") {
          trackCheckboxEvent(input, "FilterShowClosed", "ShowClosed");
        } else if (input.name === "category") {
          trackCheckboxEvent(input, "FilterCategory", CATEGORY_NAMES[input.value] || input.value);
        }
        showLoadingIndicator();
      });
    }

    var reset = document.getElementById("reset-filters");
    if (reset) {
      reset.addEventListener("click", function () {
        resetFormToDefaults();
        showLoadingIndicator();
      });
    }
  });

  document.addEventListener("htmx:afterSwap", function (evt) {
    if (evt.detail.target.id === "dossier-results") {
      FollowUpForm.init(evt.detail.target);
      initRowClick(evt.detail.target);
      initAnalyticsTracking(evt.detail.target);
    }
  });

  document.addEventListener("htmx:historyRestore", function () {
    syncFormFromUrl();
  });
})();
