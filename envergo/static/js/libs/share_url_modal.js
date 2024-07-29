/**
 * Handle the "share this url" modal dialog.
 *
 * Copy the input url to the clipboard on the button click
 * Optionaly shorten the url using the UrlMapping API
 *
 * Note that UrlMapping can be undefined if the file was not loaded
 */
(function (exports, _paq, UrlMapping) {
  'use strict';

  const ShareModal = function (dialogElt, shortenUrl) {
    this.dialogElt = dialogElt;
    this.urlInput = dialogElt.querySelector("input[type=url]");
    this.shareBtn = dialogElt.querySelector("button[type=submit]");
    this.firstDisclosed = true;
    this.shortenUrl = shortenUrl;
  };
  exports.ShareModal = ShareModal;

  ShareModal.prototype.init = function () {
    this.shareBtn.addEventListener('click', this.copyUrlToClipboard.bind(this));
    this.dialogElt.addEventListener('dsfr.disclose', this.onModalDisclose.bind(this));
    this.dialogElt.addEventListener('dsfr.conceal', this.onModalConceal.bind(this));
  };

  ShareModal.prototype.onModalDisclose = function () {
    _paq.push(['trackEvent', 'ShareDialog', 'Disclose']);

    // Optionaly replacing current url with a short url
    if (this.firstDisclosed && this.shortenUrl && UrlMapping) {
      const mapping = new UrlMapping();
      mapping.create(this.urlInput.value).then((json) => {
        this.urlInput.value = json.short_url;
      }).catch((error) => {
        console.log("Cannot create url mapping", error);
      });
    }

    this.firstDisclosed = false;
  };

  ShareModal.prototype.onModalConceal = function () {
    _paq.push(['trackEvent', 'ShareDialog', 'Conceal']);
  };

  ShareModal.prototype.copyUrlToClipboard = function () {
    this.urlInput.focus();
    this.urlInput.select();
    document.execCommand("copy");

    this.shareBtn.textContent = 'Le lien a bien été copié dans le presse-papier';
    this.shareBtn.classList.add('fr-btn--icon-left');
    this.shareBtn.classList.add('fr-icon-thumb-up-fill');

    _paq.push(['trackEvent', 'ShareDialog', 'UrlCopy']);
  };

})(this, window._paq, window.UrlMapping);

window.addEventListener('load', function () {
  const dialogElt = document.getElementById(window.SHARE_MODAL_DIALOG_ID);
  const shortenUrl = dialogElt.getAttribute('data-shorten-url') == "true";
  var shareModal = new ShareModal(dialogElt, shortenUrl);
  shareModal.init();
});
