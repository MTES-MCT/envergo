(function (exports) {
  'use strict';

  const CopyToClipboardButtons = function (btnsElement, textToCopy, sucessMessage, disabledMessage) {
    this.btnsElement = btnsElement;
    this.textToCopy = textToCopy;
    this.sucessMessage = sucessMessage;
    this.disabledMessage = disabledMessage;
  };
  exports.CopyToClipboardButtons = CopyToClipboardButtons;

  CopyToClipboardButtons.prototype.init = function () {
    this.btnsElement.forEach(copyButton => {
        // The `navigator.clipboard` API is only available on `https` urls
        if (navigator.clipboard !== undefined) {
          copyButton.addEventListener('click', () => {
            let btnText = copyButton.innerText;
            navigator.clipboard.writeText(this.textToCopy).then(() => {
              copyButton.innerText = this.sucessMessage;
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
    const textToCopy = window.TEXT_TO_COPY || "";
    const sucessMessage = window.SUCCESSFUL_COPY_MESSAGE || "Copié !";
    const disabledMessage = window.COPY_DISABLED_MESSAGE || "Copie impossible";
    const buttons = document.querySelectorAll(".btn--copy-to-clipboard");
    const copyToClipboardButtons = new CopyToClipboardButtons(buttons, textToCopy, sucessMessage, disabledMessage);
    copyToClipboardButtons.init();
  });
})();
