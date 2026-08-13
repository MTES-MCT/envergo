(function (exports) {
  'use strict';

  // The « Éviter / réduire » block: when the motif changes, swap the visible
  // message variant and uncheck the box, so the user acknowledges the message
  // matching their actual motif.
  const EviterReduire = function (sectionElt, form) {
    this.form = form;
    this.checkbox = sectionElt.querySelector('input[type=checkbox][name=eviter_reduire]');
    this.variants = sectionElt.querySelectorAll('.eviter-reduire-motif');
  };
  exports.EviterReduire = EviterReduire;

  EviterReduire.prototype.init = function () {
    const onMotifChange = this.onMotifChange.bind(this);
    const motifRadios = this.form.querySelectorAll('input[type=radio][name=motif]');
    motifRadios.forEach(function (radio) {
      radio.addEventListener('change', onMotifChange);
    });
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
