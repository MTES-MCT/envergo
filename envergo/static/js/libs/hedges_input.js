(function (window) {
  "use strict";

  let modalId = "hedge-input-modal";
  let btnClass = ".hedge-input-open-btn";

  /**
   * Create and manage the hedge ui modal / iframe.
   */
  var HedgeInputModal = function (iframeUrl, redirectUrl, onSubmitCallback) {
    this.modal = document.getElementById(modalId);
    this.btns = document.querySelectorAll(btnClass);
    this.iframeUrl = iframeUrl;
    this.redirectUrl = redirectUrl;
    this.onSubmitCallback = onSubmitCallback.bind(this) || function (hedgeData) { };

    this.btns.forEach(btn => {
      btn.addEventListener("click", this.open.bind(this));
    });

    window.addEventListener("message", this.onMessage.bind(this));

    if (window.location.hash === '#plantation') {
      this.open();
    }
  };

  HedgeInputModal.prototype.createIframe = function () {
    let iframe = document.createElement("iframe");
    iframe.id = "hedge-input-iframe";
    iframe.width = "100%";
    iframe.height = "100%";
    iframe.allowFullscreen = true;
    iframe.src = this.iframeUrl;

    iframe.addEventListener("load", function () {
      this.modal.classList.add("loaded");
    }.bind(this));

    this.iframe = iframe;
  }

  HedgeInputModal.prototype.open = function () {
    this.createIframe();
    this.modal.showModal();
    this.modal.appendChild(this.iframe);
  };

  HedgeInputModal.prototype.close = function () {
    this.modal.close();
    this.iframe.remove();
    this.modal.classList.remove("loaded");
  };

  HedgeInputModal.prototype.onMessage = function (event) {
    console.log(event.data);

    // Ignore messages from other windows
    if (event.origin !== window.location.origin) {
      return;
    }

    if (event.data.action === "cancel") {
      this.close();
    }

    if (event.data.input_id) {
      this.onSubmitCallback(event.data);

      if (this.redirectUrl) {
        const query = new URLSearchParams(window.location.search);
        query.set("haies", event.data.input_id);
        const redirectUrl = URL(this.redirectUrl);
        redirectUrl.search = query;
        window.location.href = redirectUrl;
      } else {
        this.close();
      }
    }
  };

  window.HedgeInputModal = HedgeInputModal;
}(window));
