// Disables the form submit button upon submission
(function (exports) {
  'use strict';

  const SpinnerForm = function (formElt) {
    this.formElt = formElt;
    this.formElt.addEventListener('submit', this.deactivate.bind(this));
    this.buttonElt = formElt.querySelector('[type=submit]');

    exports.addEventListener("pageshow", this.onPageShow.bind(this));
  };
  exports.SpinnerForm = SpinnerForm;

  SpinnerForm.prototype.activate = function () {
    this.buttonElt.disabled = false;
    this.buttonElt.classList.remove("icon-spinner");
    let textElt = this.formElt.querySelector('.submit-feedback-hint-text');
    if (textElt) {
      textElt.remove();
    }
  };

  SpinnerForm.prototype.deactivate = function (evt) {
    this.buttonElt.disabled = true;
    this.buttonElt.classList.add("icon-spinner");

    let textElt = document.createElement('span');
    textElt.innerHTML = 'Chargement en cours…';
    textElt.classList.add("fr-hint-text");
    textElt.classList.add("submit-feedback-hint-text");
    this.buttonElt.insertAdjacentElement("afterend", textElt);
  };

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
  };

})(this);

// Show a spinner on a link
(function (exports) {
  'use strict';

  const SpinnerLink = function (linkElt) {
    this.linkElt = linkElt;
    this.linkElt.addEventListener('click', this.deactivate.bind(this));

    exports.addEventListener("pageshow", this.onPageShow.bind(this));
  };
  exports.SpinnerLink = SpinnerLink;

  SpinnerLink.prototype.activate = function () {
    this.linkElt.classList.remove("icon-spinner");
    let textElt = this.linkElt.parentNode.querySelector('.submit-feedback-hint-text');
    if (textElt) {
      textElt.remove();
    }
  };

  SpinnerLink.prototype.deactivate = function (evt) {
    this.linkElt.classList.add("icon-spinner");

    let textElt = document.createElement('span');
    textElt.innerHTML = 'Chargement en cours…';
    textElt.classList.add("fr-hint-text");
    textElt.classList.add("submit-feedback-hint-text");
    this.linkElt.insertAdjacentElement("afterend", textElt);
  };

  SpinnerLink.prototype.onPageShow = function (event) {
    // Make sure the link is reactivated on page return
    if (event.persisted) {
      this.activate();
    }
  };

})(this);

window.addEventListener("load", function () {
  let links = document.querySelectorAll(".spinner-link");
  links.forEach((link) => {
    new SpinnerLink(link);
  });

  let forms = document.querySelectorAll(".spinner-form");
  forms.forEach((form) => {
    new SpinnerForm(form);
  });
});
