window.addEventListener('load', function () {

  var form = document.getElementById(DROPZONE_FORM);
  var field = document.getElementById(DROPZONE_FIELD);
  var submitBtn = form.querySelector('button[type=submit]');
  var previewElt = document.getElementById('dropzone-previews');
  var uploadedData = JSON.parse(document.getElementById('uploaded-files').textContent);

  form.classList.add('dropzone');
  previewElt.classList.add('dropzone');

  var dropzone = new Dropzone(form, {
    url: DROPZONE_UPLOAD_URL,
    paramName: function () { return 'additional_files'; },
    maxFilesize: 20,
    maxFiles: DROPZONE_MAX_FILES,
    acceptedFiles: 'image/*,application/pdf,application/zip',
    autoProcessQueue: true,
    uploadMultiple: false,
    parallelUploads: 100,
    addRemoveLinks: true,
    previewsContainer: previewElt,
    clickable: previewElt,
    createImageThumbnails: false,

    dictDefaultMessage: "Cliquez ou glissez-déposez vos fichiers ici.",
    dictRemoveFile: "Supprimer",
    dictFileTooBig: "Ce fichier est trop volumineux ({{filesize}} Mo). Maximum : {{maxFilesize}} Mo.",
    dictInvalidFileType: "Ce type de fichier n'est pas autorisé.",
    dictResponseError: "Ce fichier n'a pas pu être envoyé à cause d'une erreur du serveur.",
    dictCancelUpload: "Annuler l'envoi",
    dictCancelUploadConfirmation: "Êtes vous certain(e) de vouloir annuler l'envoi ?",
    dictMaxFilesExceeded: "Vous ne pouvez pas envoyer plus de fichiers.",

    init: function () {

      this.errors = {};

      // Display previously uploaded files in the upload preview
      uploadedData.forEach(function (data) {
        this.options.addedfile.call(this, data);
        this.emit('complete', data);
      }.bind(this));
      this.options.maxFiles -= uploadedData.length;
      this._updateMaxFilesReachedClass();

      // Disable the form while files are being uploaded
      this.on("addedfiles", function (files) {
        this.disableForm();
      }.bind(this));

      // Re-enable the form when all files have been uploaded
      this.on("queuecomplete", function (files, response, evt) {
        this.enableForm();
      }.bind(this));

      // Make sure the form cannot be submitted while files are being uploaded
      form.addEventListener('submit', function (evt) {
        if (this.getQueuedFiles().length > 0) {
          evt.preventDefault();
          evt.stopPropagation();
        }
      }.bind(this));

      // Attach the uploaded file saved object id to the js object
      // This way, we can make sure the "remove file" button will work
      this.on("success", function (file, response) {
        file.id = response.id;
      });

      this.on("error", function (file, message) {
        this.errors[file.upload.uuid] = file;
        form.classList.add('has-errors');
      }.bind(this));

      this.on('maxfilesreached', function () { }.bind(this));

      this.on('maxfilesexceeded', function (file) { }.bind(this));

      // Send a request to the server to request the file deletion
      this.on("removedfile", function (file) {

        // If the file had failed to upload, remove it from the errors list
        if (file.upload) {
          let uuid = file.upload.uuid;
          if (uuid in this.errors) {
            delete this.errors[uuid];
            if (Object.keys(this.errors).length == 0) {
              form.classList.remove('has-errors');
            }
          }
        }

        if (file.id) {
          // Remove the file from the server
          fetch(`${DROPZONE_UPLOAD_URL}?file_id=${file.id}`, { method: 'DELETE' })
            .then(function (response) {
              if (!response.ok) {
                this.options.addedfile.call(this, file);
                this.options.error.call(this, file, "Ce fichier n'as pas pu être supprimé. Veuillez réessayer.");
              }
            }.bind(this));
        }

        this._updateMaxFilesReachedClass();
      }.bind(this));
    }
  });

  // Disable the confirmation form while files are being uploaded
  Dropzone.prototype.disableForm = function () {
    // Disable form submit
    submitBtn.setAttribute("disabled", "");

    // Update button message
    submitBtn.classList.remove("fr-fi-checkbox-circle-line");
    submitBtn.classList.add("fr-fi-refresh-line");
    submitBtn.classList.add("spinner");
    submitBtn.textContent = "Veuillez patienter pendant le chargement de vos fichiers";
    submitBtn.setAttribute("role", "alert");
  };

  // Reactivate the confirmation form
  Dropzone.prototype.enableForm = function () {
    submitBtn.removeAttribute("disabled");

    // Update button message
    submitBtn.classList.add("fr-fi-checkbox-circle-line");
    submitBtn.classList.remove("fr-fi-refresh-line");
    submitBtn.classList.remove("spinner");
    submitBtn.textContent = "Envoyer votre demande d'avis réglementaire";
    submitBtn.removeAttribute("role");
  };
});
