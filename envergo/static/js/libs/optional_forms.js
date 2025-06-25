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
    const activeOptionsLenght = document.querySelectorAll('.optional-form.active').length;
    optionalBadge.textContent = activeOptionsLenght
    if (activeOptionsLenght === 0) {
      optionalBadgeWrapper.classList.add("no-options");
    } else {
      optionalBadgeWrapper.classList.remove("no-options");
    }

  };
})(this);

window.addEventListener('load', function () {
  const optionalDivs = document.querySelectorAll('.optional-form');
  optionalDivs.forEach(function (div) {
    new OptionalForm(div).init();
  });
});
