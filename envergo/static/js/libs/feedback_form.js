// Use Matomo API for analytics
var _paq = window._paq || [];

// This module handles the "Is this evaluation useful" feedback form
(function(exports) {
  'use strict';

  const FeedbackModal = function(dialogElt) {
    this.dialogElt = dialogElt;
    this.form = dialogElt.querySelector('form');
  };
  exports.FeedbackModal = FeedbackModal;

  FeedbackModal.prototype.init = function() {
    this.dialogElt.addEventListener('dsfr.disclose', this.onModalDisclose.bind(this));
    this.form.addEventListener('submit', this.onFeedbackSubmit.bind(this));
  };

  FeedbackModal.prototype.onModalDisclose = function(button) {
    _paq.push(['trackEvent', 'FeedbackDialog', 'Respond']);

    // Send event to Matomo
    if (VISITOR_ID) {
      let url = FEEDBACK_RESPOND_URL;
      let headers = { 'X-CSRFToken': CSRF_TOKEN };
      let data = new FormData();
      data.append('feedback', feedback);
      let init = { method: 'POST', body: data, headers: headers };
      let response = fetch(url, init);
    }
  };

  FeedbackModal.prototype.onFeedbackSubmit = function(button) {
    _paq.push(['trackEvent', 'FeedbackDialog', 'FormSubmit']);
  };

})(this);

window.addEventListener('load', function() {
  const dialogs = document.querySelectorAll(FEEDBACK_MODAL_DIALOGS);
  dialogs.forEach(dialog => {
    let feedbackModal = new FeedbackModal(dialogElt);
    feedbackModal.init();
  });
});
