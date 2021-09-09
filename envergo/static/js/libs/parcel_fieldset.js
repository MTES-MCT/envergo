/**
 * Handles the dynamic parcel formset feature.
 */
(function(exports) {
  'use strict';

  const Formset = function(formPrefix) {
    this.formPrefix = formPrefix;
    this.inputs = {
      totalFormsInput: document.getElementById(`id_${formPrefix}-TOTAL_FORMS`),
      initialFormsInput: document.getElementById(`id_${formPrefix}-INITIAL_FORMS`),
      minNumFormsInput: document.getElementById(`id_${formPrefix}-MIN_NUM_FORMS`),
      maxNumFormsInput: document.getElementById(`id_${formPrefix}-MAX_NUM_FORMS`),
    };
    this.formTemplate = document.getElementById(`tpl-form-${formPrefix}`);
    this.formset = document.getElementById(`formset-${formPrefix}`);
    this.addBtn = document.getElementById('btn-add-parcel');
    this.addBtn.addEventListener('click', this.onAddFormButtonClicked.bind(this));

    this.state = {
      totalForms: parseInt(this.inputs.totalFormsInput.value),
      selectedCitycode: '',
    };

    window.addEventListener('EnvErgo:citycode_selected', this.onCitycodeSelected.bind(this));
  };
  exports.Formset = Formset;

  /**
   * Update the application state by increasing the number of required forms.
   */
  Formset.prototype.onAddFormButtonClicked = function(e) {
    this.state.totalForms += 1;
    this.render();
  };

  /**
   * Update the dom depending on current state
   */
  Formset.prototype.render = function() {
    const nbCurrentForms = parseInt(this.inputs.totalFormsInput.value);
    const nbTargetForms = this.state.totalForms;
    const delta = nbTargetForms - nbCurrentForms;

    // Use the empty form template to add new forms to the formset
    for (let i = 0; i < delta; i++) {
      let formId = nbCurrentForms + i;
      const newForm = this.formTemplate.cloneNode(true);
      newForm.innerHTML = newForm.innerHTML.replaceAll('__prefix__', formId);
      this.formset.appendChild(newForm.content);

    }

    // Update the TOTAl_FORMS input value
    this.inputs.totalFormsInput.value = nbTargetForms;

    // Update empty commue fields with the selected citycode
    const inputs = document.querySelectorAll('input[name$=-commune]');
    inputs.forEach(function(input) {
      if (input.value === '') {
        input.value = this.state.selectedCitycode;
      }
    }.bind(this));
  };

  Formset.prototype.onCitycodeSelected = function(e) {
    const citycode = e.detail;
    this.state.selectedCitycode = citycode;
    this.render();
  };
})(this);


window.addEventListener('load', function() {
  new Formset('parcel');
});
