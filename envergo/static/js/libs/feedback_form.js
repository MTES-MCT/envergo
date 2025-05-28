// This module handles the "Is this evaluation useful" feedback form
(function (exports, _paq) {
  'use strict';

  const FeedbackModal = function (dialogElt) {
    this.dialogElt = dialogElt;
    this.form = dialogElt.querySelector('form');
  };
  exports.FeedbackModal = FeedbackModal;

  FeedbackModal.prototype.init = function () {
    this.dialogElt.addEventListener('dsfr.disclose', this.onModalDisclose.bind(this));
    this.form.addEventListener('submit', this.onFeedbackSubmit.bind(this));
  };

  FeedbackModal.prototype.onModalDisclose = function (button) {
    _paq.push(['trackEvent', 'FeedbackDialog', 'Respond']);

    let feedbackInput = this.dialogElt.querySelector('input[name$=-feedback]');
    let feedback = feedbackInput.value;

    if (VISITOR_ID) {
      let url = FEEDBACK_RESPOND_URL;
      let headers = { 'X-CSRFToken': CSRF_TOKEN };
      let data = new FormData();
      data.append('feedback', feedback);
      data.append('moulinette_data', JSON.stringify(MOULINETTE_DATA));
      let init = { method: 'POST', body: data, headers: headers };
      let response = fetch(url, init);
    }
  };

  FeedbackModal.prototype.onFeedbackSubmit = function (event) {
    _paq.push(['trackEvent', 'FeedbackDialog', 'FormSubmit']);
    if (event.submitter) {
      event.submitter.disabled = true; // Disable the submit button to prevent multiple submissions
       let textElt = document.createElement('span');
      textElt.innerHTML = 'Envoi en cours…';
      textElt.classList.add("fr-hint-text");
      textElt.classList.add("fr-mt-2w");
      event.submitter.insertAdjacentElement("afterend", textElt);
    }

    const closeButton = this.dialogElt.querySelector('.fr-link--close');
    if(closeButton) {
      closeButton.disabled = true; // Disable the close button to prevent closing while submitting
    }
    // Escape key prevention
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    }, true);

    // Prevent clicks outside the modal from closing it
    this.dialogElt.addEventListener('click', (e) => {
      const body = this.dialogElt.querySelector('.fr-modal__body');
      if (!body.contains(e.target)) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    }, true);

  };

})(this, window._paq);

window.addEventListener('load', function () {
  const dialogs = document.querySelectorAll(FEEDBACK_MODAL_DIALOGS);
  dialogs.forEach(dialog => {
    let feedbackModal = new FeedbackModal(dialog);
    feedbackModal.init();
  });
});
