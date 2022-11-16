// Use Matomo API for analytics
var _paq = window._paq || [];

(function(exports) {
  'use strict';

  const FeedbackModal = function(dialogElt) {
    this.dialogElt = dialogElt;
  };
  exports.FeedbackModal = FeedbackModal;

  FeedbackModal.prototype.init = function() {
    this.dialogElt.addEventListener('dsfr.disclose', this.onDisclose.bind(this));
    this.dialogElt.addEventListener('dsfr.conceal', this.onConceal.bind(this));
  };

  FeedbackModal.prototype.onDisclose = function(e) {
    _paq.push(['trackEvent', 'FeedbackDialog', 'Disclose']);
  };

  FeedbackModal.prototype.onConceal = function() {
    _paq.push(['trackEvent', 'FeedbackDialog', 'Conceal']);
  };

  FeedbackModal.prototype.updateFeedbackContent = function(button) {
    let labelVal = button.getAttribute('data-label');
    let feedback = button.getAttribute('data-feedback');

    // Set the "feedback value (Oui / Non) hidden input value
    let feedbackInput = this.dialogElt.querySelector('input[name=feedback]');
    feedbackInput.value = feedback;

    // Update the feedback content label
    let label = this.dialogElt.querySelector('[for=id_message] span');
    label.innerHTML = labelVal;
  };


})(this);

window.addEventListener('load', function() {
  const dialogElt = document.getElementById(window.FEEDBACK_MODAL_DIALOG_ID);
  var feedbackModal = new FeedbackModal(dialogElt);
  feedbackModal.init();

  // We need to update the modal content depending on the clicked button
  const buttons = document.querySelectorAll(window.FEEDBACK_BUTTONS);
  buttons.forEach(button => {
    button.addEventListener('click', () => {
      feedbackModal.updateFeedbackContent(button);
    });
  });
});
