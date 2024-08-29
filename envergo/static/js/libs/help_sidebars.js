/**
 * Handle the lateral help sidebar display and hiding.
 */
window.addEventListener("load", function () {
  let helpBtns = document.querySelectorAll(".help-sidebar-button");
  let closeBtns = document.querySelectorAll(".fr-btn--close");
  let moulinetteGrid = document.getElementById("moulinette-grid");
  let sidebars = document.querySelectorAll(".help-sidebar");

  helpBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {

      sidebars.forEach(function (sidebar) {
        sidebar.classList.remove("sidebar-open");
      });

      let sidebarId = btn.attributes["aria-controls"].value;
      let sidebar = document.getElementById(sidebarId);
      sidebar.classList.add("sidebar-open");
      moulinetteGrid.classList.add("sidebar-open");
    });

    closeBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        let sidebarId = btn.attributes["aria-controls"].value;
        let sidebar = document.getElementById(sidebarId);
        sidebar.classList.remove("sidebar-open");
        moulinetteGrid.classList.remove("sidebar-open");
      });

    });
  });
});
