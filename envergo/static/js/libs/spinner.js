// Disables the form submit button upon submission
(function (exports) {
  'use strict';

  class SpinnerElement {
    constructor(elt, inner=false) {
      this.inner = inner;

      // The main node (form, link, button)
      this.elt = elt;
      // The element with the spinner icon
      this.spinnerElt = elt;

      switch (elt.nodeName) {
        case "FORM":
          elt.addEventListener('submit', this.deactivate.bind(this));
          this.spinnerElt = elt.querySelector('[type=submit]');
          break;
        case "A":
        case "BUTTON":
          elt.addEventListener('click', this.deactivate.bind(this));
          break;
      }

      this.originalText = this.spinnerElt.innerText;
      exports.addEventListener("pageshow", this.onPageShow.bind(this));
    }

    activate() {
      this.spinnerElt.disabled = false;
      this.spinnerElt.classList.remove("icon-spinner");
      if(this.inner){
         this.spinnerElt.innerText = this.originalText;
      }
      else{
        let textElt = this.spinnerElt.parentNode.querySelector('.submit-feedback-hint-text');
        if (textElt) {
          textElt.remove();
        }
      }
    }

    deactivate() {
      this.spinnerElt.disabled = true;
      this.spinnerElt.classList.add("icon-spinner");

      if(this.inner){
        this.spinnerElt.innerText = 'Chargement en cours';
      }
      else{
        let textElt = document.createElement('span');
        textElt.innerHTML = 'Chargement en cours…';
        textElt.classList.add("fr-hint-text");
        textElt.classList.add("submit-feedback-hint-text");
        this.spinnerElt.insertAdjacentElement("afterend", textElt);
      }
    }

    onPageShow(event) {
      if (event.persisted) {
        this.activate();
      }
    }
  }

  exports.SpinnerElement = SpinnerElement;
})(this);

window.addEventListener("load", function () {
  let links = document.querySelectorAll(".spinner-link");
  links.forEach((link) => {
    new SpinnerElement(link);
  });

  let innerLinks = document.querySelectorAll(".inner-spinner-link");
  innerLinks.forEach((link) => {
    new SpinnerElement(link, inner=true);
  });

  let forms = document.querySelectorAll(".spinner-form");
  forms.forEach((form) => {
    new SpinnerElement(form);
  });
});
