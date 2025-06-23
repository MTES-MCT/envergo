// Disables the form submit button upon submission
(function (exports) {
  'use strict';

  const SpinnerForm = function (formElt) {
    this.formElt = formElt;
    this.formElt.addEventListener('submit', this.deactivate.bind(this));
    this.buttonElt = formElt.querySelector('button[type=submit]');

    exports.addEventListener("pageshow", this.onPageShow.bind(this));
  };
  exports.SpinnerForm = SpinnerForm;

  SpinnerForm.prototype.onPageShow = function (event) {
    // When the form is submitted, we disable the submission button with a
    // message to make sure the user understands that the form is being
    // submitted.
    // When the user navigates back, and the page is rendered from cache,
    // the button is re-rendered deactivated.
    // In that case, we need to make sure the form can be submitted again.
    if (event.persisted) {
      this.activate();
    }
  }

  SpinnerForm.prototype.deactivate = function (evt) {
    this.buttonElt.disabled = true;
    this.buttonElt.classList.add("icon-spinner");

    let textElt = document.createElement('span');
    textElt.innerHTML = 'Simulation en cours…';
    textElt.classList.add("fr-hint-text");
    textElt.classList.add("submit-feedback-hint-text");
    this.buttonElt.insertAdjacentElement("afterend", textElt);
  };

  SpinnerForm.prototype.activate = function () {
    this.buttonElt.disabled = false;
    let textElt = this.formElt.querySelector('.submit-feedback-hint-text');
    if (textElt) {
      textElt.remove();
    }
  };

})(this);
