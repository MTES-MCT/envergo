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
  };
})(this);

window.addEventListener('load', function () {
  const optionalDivs = document.querySelectorAll('.optional-form');
  optionalDivs.forEach(function (div) {
    new OptionalForm(div).init();
  });
});
