window.addEventListener("load", function () {

  /**
   * Handle the lateral help sidebar display and hiding.
   *
   * When a sidebar button is clicked, the corresponding sidebar is shown.
   * when the sidebar is already open, it is hidden instead.
   */
  class SidebarManager {
    constructor(sidebarElts, sidebarBtns, mainContent) {
      this.sidebarElts = sidebarElts;
      this.sidebarBtns = sidebarBtns;
      this.mainContent = mainContent;

      // Keep track of the currently open sidebar
      this.currentSidebarId = undefined;

      this.sidebarBtns.forEach((sidebarBtn) => {
        sidebarBtn.addEventListener("click", this.onSidebarBtnClick.bind(this));
      });

      this.sidebarElts.forEach((sidebarElt) => {
        let closeBtn = sidebarElt.querySelector(".fr-btn--close");
        closeBtn.addEventListener("click", this.closeSidebar.bind(this));
      });
    }

    onSidebarBtnClick(evt) {
      let btn = evt.currentTarget;
      let sidebarId = btn.attributes["aria-controls"].value;

      if (this.currentSidebarId === sidebarId) {
        this.closeSidebar();
      } else {
        this.closeSidebar();
        this.openSidebar(sidebarId);
      }
    }

    // Open the selected sidebar
    openSidebar(sidebarId) {
      let sidebarElt = document.getElementById(sidebarId);
      sidebarElt.show();
      this.mainContent.classList.add("sidebar-open");

      this.currentSidebarId = sidebarId;

      // Track matomo event
      let eventId = sidebarId.replace("sidebar-", "");
      _paq.push(["trackEvent", "Form", "HelpDisclose", eventId]);
    }

    // Close the currently open sidebar (if any)
    closeSidebar() {

      if (this.currentSidebarId === undefined) {
        return;
      }

      let sidebarElt = document.getElementById(this.currentSidebarId);
      sidebarElt.close();
      this.mainContent.classList.remove("sidebar-open");

      // Track matomo event
      let eventId = this.currentSidebarId.replace("sidebar-", "");
      _paq.push(["trackEvent", "Form", "HelpConceal", eventId]);

      this.currentSidebarId = undefined;
    }
  }

  let sidebarElts = document.querySelectorAll(".help-sidebar");
  let sidebarBtns = document.querySelectorAll(".help-sidebar-button");
  let moulinetteGrid = document.getElementById("moulinette-grid");
  new SidebarManager(sidebarElts, sidebarBtns, moulinetteGrid);
});
