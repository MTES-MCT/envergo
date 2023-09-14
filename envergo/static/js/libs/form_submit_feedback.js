// Disables the form submit button upon submission
(function (exports) {
  'use strict';

  const SimulationForm = function (formElt) {
    this.formElt = formElt;
    this.buttonElt = formElt.querySelector('button[type=submit]');
  };
  exports.SimulationForm = SimulationForm;

  SimulationForm.prototype.init = function () {
    this.formElt.addEventListener('submit', this.onFormSubmit.bind(this));
  };

  SimulationForm.prototype.onFormSubmit = function (evt) {
    this.buttonElt.disabled = true;
    this.buttonElt.classList.add("fr-mr-1w");

    let textElt = document.createElement('span');
    textElt.innerHTML = 'Simulation en cours…';
    textElt.style.display = "inline";
    textElt.classList.add("fr-hint-text");
    this.buttonElt.insertAdjacentElement("afterend", textElt);
  };

})(this);

window.addEventListener('load', function () {
  const form = document.getElementById(SIMULATION_FORM_ID);
  new SimulationForm(form).init();
});
