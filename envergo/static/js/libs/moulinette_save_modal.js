(function(exports) {
  'use strict';

  const SaveModal = function(dialogElt) {
    this.dialogElt = dialogElt;
  };
  exports.SaveModal = SaveModal;

  SaveModal.prototype.init = function() {
    this.dialogElt.addEventListener('dsfr.disclose', this.onModalDisclose.bind(this));
    this.dialogElt.addEventListener('dsfr.conceal', this.onModalConceal.bind(this));
  };

  SaveModal.prototype.onModalDisclose = function() {
    let data = new FormData();
    data.append("category", "save");
    data.append("action", "click");
    data.append("metadata", JSON.stringify({}));

    let token = CSRF_TOKEN;
    let headers = { "X-CSRFToken": token };

    let url = EVENTS_URL;
    fetch(url, { headers: headers, body: data, method: 'POST' });
  };

  SaveModal.prototype.onModalConceal = function() {};

})(this);

window.addEventListener('load', function() {
  const dialogElt = document.getElementById(window.SAVE_MODAL_DIALOG_ID);
  var saveModal = new SaveModal(dialogElt);
  saveModal.init();
});
