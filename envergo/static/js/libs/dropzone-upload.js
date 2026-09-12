/**
 * Shared setup for the dropzone upload forms.
 *
 * Both the public "demande d'avis" wizard and the admin map import batch page
 * upload one file per request to a django view returning {id} or {error}, and
 * delete with `DELETE ?file_id=`. Everything they have in common lives here;
 * each page only provides what actually differs (field name, accepted types,
 * timeout) plus an optional `onInit` hook for page specific behaviour.
 *
 * Expects in the page: a form, a `#dropzone-previews` container and a
 * `#uploaded-files` json_script holding the already uploaded files.
 */
window.initDropzoneUpload = function (options) {
  var form = document.getElementById(options.formId);
  var previewElt = document.getElementById('dropzone-previews');
  var uploadedData = JSON.parse(document.getElementById('uploaded-files').textContent);

  // The csrf cookie is httponly, so the token has to be read from the form.
  var csrfInput = form.querySelector('input[name=csrfmiddlewaretoken]');
  var headers = csrfInput ? { 'X-CSRFToken': csrfInput.value } : null;

  // The upload url may already carry a query string (the avis one is
  // obfuscated with ?clef=<uuid>), so the separator cannot be hardcoded.
  var deleteUrl = function (fileId) {
    var separator = options.uploadUrl.indexOf('?') === -1 ? '?' : '&';
    return options.uploadUrl + separator + 'file_id=' + fileId;
  };

  form.classList.add('dropzone');
  previewElt.classList.add('dropzone');

  var config = {
    url: options.uploadUrl,
    paramName: function () { return options.paramName; },
    maxFilesize: options.maxFilesize,
    maxFiles: options.maxFiles,
    acceptedFiles: options.acceptedFiles,
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
    dictInvalidFileType: options.dictInvalidFileType || "Ce type de fichier n'est pas autorisé.",
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
          fetch(deleteUrl(file.id), {
            method: 'DELETE',
            headers: headers || {},
          })
            .then(function (response) {
              if (!response.ok) {
                this.options.addedfile.call(this, file);
                this.options.error.call(this, file, "Ce fichier n'a pas pu être supprimé. Veuillez réessayer.");
              }
            }.bind(this));
        }

        this._updateMaxFilesReachedClass();
      }.bind(this));

      if (options.onInit) {
        options.onInit.call(this, this, form);
      }
    }
  };

  if (headers) {
    config.headers = headers;
  }

  // Large files can take several minutes to upload, and the dropzone default
  // of 30s would abort them.
  if (options.timeout !== undefined) {
    config.timeout = options.timeout;
  }

  return new Dropzone(form, config);
};
