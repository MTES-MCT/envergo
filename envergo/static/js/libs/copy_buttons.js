(function (exports) {
  'use strict';

  const CopyToClipboardButtons = function (btnsElement, successMessage, disabledMessage) {
    this.btnsElement = btnsElement;
    this.successMessage = successMessage;
    this.disabledMessage = disabledMessage;
  };
  exports.CopyToClipboardButtons = CopyToClipboardButtons;

  CopyToClipboardButtons.prototype.init = function () {
    this.btnsElement.forEach(copyButton => {
      // The `navigator.clipboard` API is only available on `https` urls
      if (navigator.clipboard !== undefined) {
        copyButton.addEventListener('click', () => {
          let btnText = copyButton.innerText;
          const textToCopy = copyButton.getAttribute("data-clipboard-text");
          navigator.clipboard.writeText(textToCopy).then(() => {
            copyButton.innerText = this.successMessage;
          });

          setTimeout(function () {
            copyButton.innerText = btnText;
          }, 2000);
        });
      } else {
        copyButton.innerText = this.disabledMessage;
        copyButton.disabled = true;
      }
    });
  };
})(this);

(function () {
  // a script to add interactions on copy to clipboard buttons
  window.addEventListener('load', function () {
    let successMessage = "Copié";
    if (window.SUCCESSFUL_COPY_MESSAGE !== undefined) successMessage = window.SUCCESSFUL_COPY_MESSAGE;

    let disabledMessage = "Copie impossible";
    if (window.COPY_DISABLED_MESSAGE !== undefined) disabledMessage = window.COPY_DISABLED_MESSAGE;

    const buttons = document.querySelectorAll(".btn--copy-to-clipboard");
    const copyToClipboardButtons = new CopyToClipboardButtons(buttons, successMessage, disabledMessage);
    copyToClipboardButtons.init();
  });
})();
