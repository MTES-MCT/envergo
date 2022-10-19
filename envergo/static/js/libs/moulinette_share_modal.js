(function(exports, L) {
  'use strict';

  /**
   * Initialize the leaflet maps for the moulinette result page.
   */
  const ShareModal = function(dialogElt) {
    this.dialogElt = dialogElt;
  };
  exports.ShareModal = ShareModal;

  ShareModal.prototype.init = function() {};

})(this, L);

window.addEventListener('load', function() {
  const dialogElt = document.getElementById(window.SHARE_MODAL_DIALOG_ID);
  var shareModal = new ShareModal(dialogElt);
  shareModal.init();
});
