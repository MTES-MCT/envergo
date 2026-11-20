window.addEventListener('load', function () {

  var submitBtn = document
    .getElementById(DROPZONE_FORM)
    .querySelector('button[type=submit]');

  initDropzoneUpload({
    formId: DROPZONE_FORM,
    uploadUrl: DROPZONE_UPLOAD_URL,
    maxFiles: DROPZONE_MAX_FILES,
    maxFilesize: DROPZONE_MAX_FILESIZE,
    paramName: 'additional_files',
    acceptedFiles: 'image/*,application/pdf,application/zip,application/x-zip-compressed,application/octet-stream,.zip',

    onInit: function (dropzone, form) {
      var disableForm = function () {
        if (!submitBtn) {
          return;
        }
        submitBtn.setAttribute("disabled", "");

        // Update button message
        submitBtn.classList.remove("fr-fi-checkbox-circle-line");
        submitBtn.classList.add("fr-fi-refresh-line");
        submitBtn.classList.add("spinner");
        submitBtn.textContent = "Veuillez patienter pendant le chargement de vos fichiers";
        submitBtn.setAttribute("role", "alert");
      };

      var enableForm = function () {
        if (!submitBtn) {
          return;
        }
        submitBtn.removeAttribute("disabled");

        // Update button message
        submitBtn.classList.add("fr-fi-checkbox-circle-line");
        submitBtn.classList.remove("fr-fi-refresh-line");
        submitBtn.classList.remove("spinner");
        submitBtn.textContent = "Envoyer votre demande d'avis réglementaire";
        submitBtn.removeAttribute("role");
      };

      // Disable the confirmation form while files are being uploaded
      dropzone.on("addedfiles", disableForm);
      dropzone.on("queuecomplete", enableForm);

      // Make sure the form cannot be submitted while files are being uploaded
      form.addEventListener('submit', function (evt) {
        if (dropzone.getQueuedFiles().length > 0) {
          evt.preventDefault();
          evt.stopPropagation();
        }
      });
    },
  });
});
