(function(exports) {
  'use strict';

  const ShareModal = function(dialogElt) {
    this.dialogElt = dialogElt;
    this.urlInput = dialogElt.querySelector("input[type=url]");
    this.shareBtn = dialogElt.querySelector("button[type=submit]");
  };
  exports.ShareModal = ShareModal;

  ShareModal.prototype.init = function() {
    this.shareBtn.addEventListener('click', this.copyUrlToClipboard.bind(this));
  };

  ShareModal.prototype.copyUrlToClipboard = function() {
    this.urlInput.focus();
    this.urlInput.select();
    document.execCommand("copy");

    this.shareBtn.textContent = 'Le lien a bien été copié dans le presse-papier';
    this.shareBtn.classList.add('fr-btn--icon-left');
    this.shareBtn.classList.add('fr-icon-thumb-up-fill');
  };

})(this);

window.addEventListener('load', function() {
  const dialogElt = document.getElementById(window.SHARE_MODAL_DIALOG_ID);
  var shareModal = new ShareModal(dialogElt);
  shareModal.init();
});
