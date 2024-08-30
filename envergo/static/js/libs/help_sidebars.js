/**
 * Handle the lateral help sidebar display and hiding.
 */
window.addEventListener("load", function () {
  let helpBtns = document.querySelectorAll(".help-sidebar-button");
  let closeBtns = document.querySelectorAll(".fr-btn--close");
  let moulinetteGrid = document.getElementById("moulinette-grid");
  let sidebars = document.querySelectorAll(".help-sidebar");

  // When a help button is clicked…
  helpBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {

      // Close all currently open sidebars
      sidebars.forEach(function (sidebar) {
        sidebar.close();
      });

      // Display the sidebar that corresponds to the current field
      let sidebarId = btn.attributes["aria-controls"].value;
      let sidebar = document.getElementById(sidebarId);
      sidebar.classList.add("sidebar-open");
      sidebar.show();

      // Also add a class to the main moulinette content so we can adapt
      // it's display
      moulinetteGrid.classList.add("sidebar-open");

      // Track matomo event
      let eventId = sidebarId.replace("sidebar-", "");
      _paq.push(["trackEvent", "Form", "HelpDisclose", eventId]);
    });

    closeBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        let sidebarId = btn.attributes["aria-controls"].value;
        let sidebar = document.getElementById(sidebarId);
        sidebar.close();
        moulinetteGrid.classList.remove("sidebar-open");

        // Track matomo event
        let eventId = sidebarId.replace("sidebar-", "");
        _paq.push(["trackEvent", "Form", "HelpConceal", eventId]);
      });
    });
  });
});
