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
      selectedCommune: {
        name: '',
        code: ''
      },
    };

    this.citycodeHintElement = undefined;

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
    this.renderFormset();
    this.renderCitycodeHint();
    this.renderCitycodeFields();
  };

  Formset.prototype.renderFormset = function() {
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
  };

  /**
   * Display the selected address's corresponding city code
   */
  Formset.prototype.renderCitycodeHint = function() {
    if (this.citycodeHintElement === undefined) {
      this.citycodeHintElement = document.createElement('p');
      this.citycodeHintElement.classList.add('fr-alert', 'fr-alert--info', 'fr-mt-3w');
    }

    const name = this.state.selectedCommune.name;
    const code = this.state.selectedCommune.code;
    this.citycodeHintElement.innerHTML = `Code commune pour ${name} : <strong>${code}</strong>`;

    this.formset.parentElement.insertBefore(this.citycodeHintElement, this.formset);
  };

  /**
   * Pre-fill the city code fields.
   */
  Formset.prototype.renderCitycodeFields = function() {
    const fields = this.formset.querySelectorAll('input[name$=commune]');
    fields.forEach(function(field) {
      if (field.value === '') {
        field.value = this.state.selectedCommune.code;
      }
    }.bind(this));
  };

  /**
   * React when a new address is selected.
   */
  Formset.prototype.onCitycodeSelected = function(e) {
    const { communeName, citycode } = e.detail;
    this.state.selectedCommune = {
      name: communeName,
      code: citycode
    };
    this.render();
  };

})(this);


window.addEventListener('load', function() {
  new Formset('parcel');
});
