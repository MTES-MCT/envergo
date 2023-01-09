// Use Matomo API for analytics
var _paq = window._paq || [];

(function(exports) {
  'use strict';

  const FeedbackModal = function(dialogElt) {
    this.dialogElt = dialogElt;
    this.form = dialogElt.querySelector('form');
  };
  exports.FeedbackModal = FeedbackModal;

  FeedbackModal.prototype.init = function() {
    this.dialogElt.addEventListener('dsfr.disclose', this.onDisclose.bind(this));
    this.dialogElt.addEventListener('dsfr.conceal', this.onConceal.bind(this));
    this.form.addEventListener('submit', this.onFeedbackSubmit.bind(this));
  };

  FeedbackModal.prototype.onFeedbackRespond = function(button) {
    _paq.push(['trackEvent', 'FeedbackDialog', 'Respond']);

    let labelVal = button.getAttribute('data-label');
    let feedback = button.getAttribute('data-feedback');

    // Set the "feedback value (Oui / Non) hidden input value
    let feedbackInput = this.dialogElt.querySelector('input[name=feedback]');
    feedbackInput.value = feedback;

    // Update the feedback content label
    let label = this.dialogElt.querySelector('[for=id_message] span');
    label.innerHTML = labelVal;

    let url = FEEDBACK_RESPOND_URL;
    let headers = { 'X-CSRFToken': CSRF_TOKEN };
    let data = new FormData();
    data.append('feedback', feedback);
    let init = { method: 'POST', body: data, headers: headers };
    let response = fetch(url, init);
  };

  FeedbackModal.prototype.onFeedbackSubmit = function(button) {
    _paq.push(['trackEvent', 'FeedbackDialog', 'FormSubmit']);
  };

})(this);

window.addEventListener('load', function() {
  const dialogElt = document.getElementById(FEEDBACK_MODAL_DIALOG_ID);
  if (dialogElt) {
    let feedbackModal = new FeedbackModal(dialogElt);
    feedbackModal.init();

    // We need to update the modal content depending on the clicked button
    const buttons = document.querySelectorAll(FEEDBACK_BUTTONS);
    buttons.forEach(button => {
      button.addEventListener('click', () => {
        feedbackModal.onFeedbackRespond(button);
      });
    });
  }
});
