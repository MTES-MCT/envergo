(function () {
  window.addEventListener('EnvErgo:citycode_selected', function (event) {
    this.inputId = `id_${DEPARTMENT_FIELD_NAME}`;
    this.inputElement = document.getElementById(this.inputId);
    const department = event.detail.department;
    this.inputElement.value=department;
  });
})();
