(function (exports) {
  'use strict';

  const OptionalForm = function (divElt) {
    this.divElt = divElt;
    this.checkbox = divElt.querySelector('input[type=checkbox][name$=activate]');
  };
  exports.OptionalForm = OptionalForm;

  OptionalForm.prototype.init = function () {
    this.checkbox.addEventListener('change', this.onCheckboxChange.bind(this));
    this.onCheckboxChange();
  };

  OptionalForm.prototype.onCheckboxChange = function (evt) {

    if (this.checkbox.checked) {
      this.divElt.classList.add("active");
    } else {
      this.divElt.classList.remove("active");
    }

    const optionalBadgeWrapper = document.querySelector('#option-count-wrapper');
    const optionalBadge = document.querySelector('#option-count');
    const activeOptionsLength = document.querySelectorAll('.optional-form.active').length;
    if (activeOptionsLength === 0) {
      optionalBadge.textContent = "";
      optionalBadgeWrapper.classList.add("no-options");
    } else {
      if (activeOptionsLength === 1) {
        optionalBadge.textContent = "1 option activée";
      } else if (activeOptionsLength > 1) {
        optionalBadge.textContent = activeOptionsLength + " options activées";
      }
      optionalBadgeWrapper.classList.remove("no-options");
    }

  };
})(this);

window.addEventListener('load', function () {
  const optionalDivs = document.querySelectorAll('.optional-form');
  optionalDivs.forEach(function (div) {
    new OptionalForm(div).init();
  });

  // Expand if errors on optional form
  const optionalAccordion = document.querySelector('#accordion-optional-forms');
  const optionalDivsGroupError = document.querySelectorAll('.optional-form .fr-input-group--error');
  if (optionalDivsGroupError.length > 0) {
    dsfr(optionalAccordion).collapse.disclose();
  }
});

// Log an event when optionnal questions are expanded or collapsed
window.addEventListener('dsfr.disclose', function (evt) {
  _paq.push(['trackEvent', 'Form', 'OptQuestionsExpand']);
}, { once: true });

window.addEventListener('dsfr.conceal', function (evt) {
  _paq.push(['trackEvent', 'Form', 'OptQuestionsCollapse']);
}, { once: true });
