(function(exports, _paq) {
  'use strict';

  const ShareModal = function(dialogElt) {
    this.dialogElt = dialogElt;
    this.urlInput = dialogElt.querySelector("input[type=url]");
    this.shareBtn = dialogElt.querySelector("button[type=submit]");
  };
  exports.ShareModal = ShareModal;

  ShareModal.prototype.init = function() {
    this.shareBtn.addEventListener('click', this.copyUrlToClipboard.bind(this));
    this.dialogElt.addEventListener('dsfr.disclose', this.onModalDisclose.bind(this));
    this.dialogElt.addEventListener('dsfr.conceal', this.onModalConceal.bind(this));
  };

  ShareModal.prototype.onModalDisclose = function() {
    _paq.push(['trackEvent', 'ShareDialog', 'DialogDisclose']);
  };

  ShareModal.prototype.onModalConceal = function() {
    _paq.push(['trackEvent', 'ShareDialog', 'DialogConceal']);
  };

  ShareModal.prototype.copyUrlToClipboard = function() {
    this.urlInput.focus();
    this.urlInput.select();
    document.execCommand("copy");

    this.shareBtn.textContent = 'Le lien a bien été copié dans le presse-papier';
    this.shareBtn.classList.add('fr-btn--icon-left');
    this.shareBtn.classList.add('fr-icon-thumb-up-fill');

    _paq.push(['trackEvent', 'ShareDialog', 'URLCopy']);
  };

})(this, window._paq || []);

window.addEventListener('load', function() {
  const dialogElt = document.getElementById(window.SHARE_MODAL_DIALOG_ID);
  var shareModal = new ShareModal(dialogElt);
  shareModal.init();
});
