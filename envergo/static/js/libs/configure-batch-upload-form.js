window.addEventListener('load', function () {

  var form = document.getElementById(DROPZONE_FORM);
  var previewElt = document.getElementById('dropzone-previews');
  var uploadedData = JSON.parse(document.getElementById('uploaded-files').textContent);

  // The csrf cookie is httponly, so the token must be read from the form
  var csrfToken = form.querySelector('input[name=csrfmiddlewaretoken]').value;

  form.classList.add('dropzone');
  previewElt.classList.add('dropzone');

  var dropzone = new Dropzone(form, {
    url: DROPZONE_UPLOAD_URL,
    paramName: function () { return 'map_files'; },
    headers: { 'X-CSRFToken': csrfToken },
    maxFilesize: DROPZONE_MAX_FILESIZE,
    maxFiles: DROPZONE_MAX_FILES,
    acceptedFiles: '.gpkg,.zip',
    // Large map files can take several minutes to upload; the default
    // 30s timeout would abort them.
    timeout: 0,
    autoProcessQueue: true,
    uploadMultiple: false,
    parallelUploads: 1,
    addRemoveLinks: true,
    previewsContainer: previewElt,
    clickable: previewElt,
    createImageThumbnails: false,

    dictDefaultMessage: "Cliquez ou glissez-déposez vos fichiers ici.",
    dictRemoveFile: "Supprimer",
    dictFileTooBig: "Ce fichier est trop volumineux ({{filesize}} Mo). Maximum : {{maxFilesize}} Mo.",
    dictInvalidFileType: "Ce type de fichier n'est pas autorisé (.gpkg ou .zip attendu).",
    dictResponseError: "Ce fichier n'a pas pu être envoyé à cause d'une erreur du serveur.",
    dictCancelUpload: "Annuler l'envoi",
    dictCancelUploadConfirmation: "Êtes vous certain(e) de vouloir annuler l'envoi ?",
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

      // Attach the uploaded file saved object id to the js object
      // This way, we can make sure the "remove file" button will work
      this.on("success", function (file, response) {
        file.id = response.id;
      });

      this.on("error", function (file, message, xhr) {
        this.errors[file.upload.uuid] = file;
        form.classList.add('has-errors');

        if (!xhr || xhr.status === 0 || xhr.status >= 500) {
          var errorSpan = file.previewElement && file.previewElement.querySelector('.dz-error-message span');
          if (errorSpan) {
            errorSpan.textContent = "Le fichier a mis trop de temps à être envoyé. Réessayez, ou contactez-nous si le problème persiste.";
          }
        }
      }.bind(this));

      // Send a request to the server to request the file deletion
      this.on("removedfile", function (file) {

        // If the file had failed to upload, remove it from the errors lists
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
          fetch(`${DROPZONE_UPLOAD_URL}?file_id=${file.id}`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrfToken },
          })
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
});
