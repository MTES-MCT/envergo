(function () {
  window.addEventListener('Envergo:citycode_selected', function (event) {
    // populate the department field with the selected department
    this.inputId = `id_${DEPARTMENT_FIELD_NAME}`;
    this.inputElement = document.getElementById(this.inputId);
    const department = event.detail.department;
    this.inputElement.value=department;
  });

  window.addEventListener('Envergo:address_autocomplete_input', function (event) {
    // clear the department field when the user types in the address field
    this.inputId = `id_${DEPARTMENT_FIELD_NAME}`;
    this.inputElement = document.getElementById(this.inputId);
    this.inputElement.value="";
  });
})();
