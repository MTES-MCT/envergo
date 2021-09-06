(function (exports) {
    'use strict';

    const Fieldset = function (formPrefix) {
        this.formPrefix = formPrefix;
        this.inputs = {
            totalFormsInput: document.getElementById(`id_${formPrefix}-TOTAL_FORMS`),
            initialFormsInput: document.getElementById(`id_${formPrefix}-INITIAL_FORMS`),
            minNumFormsInput: document.getElementById(`id_${formPrefix}-MIN_NUM_FORMS`),
            maxNumFormsInput: document.getElementById(`id_${formPrefix}-MAX_NUM_FORMS`),
        };
        this.addBtn = document.getElementById('btn-add-parcels');
    };
    exports.Fieldset = Fieldset;
})(this);



window.onload = function () {
    new Fieldset('parcel');
};
