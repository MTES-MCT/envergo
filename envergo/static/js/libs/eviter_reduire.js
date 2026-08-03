(function (exports) {
  'use strict';

  // The « Éviter / réduire » acknowledgment block.
  //
  // The message depends on the "motif" value.
  // The the value change, swap the message and uncheck the "J'ai compris" input.
  const EviterReduire = function (sectionElt, form) {
    this.sectionElt = sectionElt;
    this.form = form;
    this.checkbox = sectionElt.querySelector('input[type=checkbox][name=eviter_reduire]');
    this.variants = sectionElt.querySelectorAll('.eviter-reduire-motif');
  };
  exports.EviterReduire = EviterReduire;

  EviterReduire.prototype.init = function () {
    const motifRadios = this.form.querySelectorAll('input[type=radio][name=motif]');
    motifRadios.forEach(function (radio) {
      radio.addEventListener('change', this.onMotifChange.bind(this));
    }, this);
  };

  EviterReduire.prototype.onMotifChange = function (evt) {
    const motif = evt.target.value;
    this.variants.forEach(function (variant) {
      variant.hidden = variant.dataset.motif !== motif;
    });
    this.checkbox.checked = false;
  };
})(this);

window.addEventListener('load', function () {
  const section = document.querySelector('#eviter-reduire');
  const form = section && section.closest('form');
  if (form) {
    new EviterReduire(section, form).init();
  }
});
