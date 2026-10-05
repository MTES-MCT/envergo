// Expand the optional forms accordion when it contains errors.
(function () {
  'use strict';

  const optionalAccordion = document.querySelector('#accordion-optional-forms');
  const optionalDivsGroupError = document.querySelectorAll('.optional-form .fr-input-group--error');
  if (optionalAccordion && optionalDivsGroupError.length > 0) {
    dsfr(optionalAccordion).collapse.disclose();
  }
})();
