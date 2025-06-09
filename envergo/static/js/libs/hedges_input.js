(function (window) {
  "use strict";

  let modalId = "hedge-input-modal";
  let btnClass = ".hedge-input-open-btn";

  /**
   * Create and manage the hedge ui modal / iframe.
   */
  var HedgeInputModal = function (iframeUrl, redirectUrl, submitCallback) {
    this.modal = document.getElementById(modalId);
    this.btns = document.querySelectorAll(btnClass);
    this.iframeUrl = iframeUrl;
    this.redirectUrl = redirectUrl;

    if (submitCallback === undefined) {
      this.onSubmitCallback = function (data) { };
    } else {
      this.onSubmitCallback = submitCallback.bind(this);
    }

    this.btns.forEach(btn => {
      btn.addEventListener("click", this.open.bind(this));
    });

    window.addEventListener("message", this.onMessage.bind(this));
  };

  // We need to create the iframe before adding it to the dom
  // because using an existing iframe messes with the history management,
  // and make the "back" and "forward" buttons unreliable.
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
        const url = new URL(window.location);
        url.pathname = this.redirectUrl;
        url.searchParams.set("haies", event.data.input_id);
        window.location.href = url;
      } else {
        this.close();
      }
    }
  };

  window.HedgeInputModal = HedgeInputModal;
}(window));
