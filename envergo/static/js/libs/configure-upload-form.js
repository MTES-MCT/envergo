window.addEventListener('load', function() {

  var form = document.getElementById(DROPZONE_FORM);
  var field = document.getElementById(DROPZONE_FIELD);
  var previewElt = document.getElementById('dropzone-previews');

  form.classList.add('dropzone');
  previewElt.classList.add('dropzone');

  var dropzone = new Dropzone(form, {
    url: DROPZONE_UPLOAD_URL,
    paramName: function() { return 'additional_files'; },
    maxFilesize: 20,
    maxFiles: 10,
    acceptedFiles: 'image/*,application/pdf,application/zip',
    autoProcessQueue: false,
    uploadMultiple: true,
    parallelUploads: 100,
    maxFiles: 100,
    addRemoveLinks: true,
    previewsContainer: previewElt,
    clickable: previewElt,

    // headers: {
    //   'X-CSRFToken': csrfToken,
    // },

    dictDefaultMessage: "Cliquez ou glissez-déposez vos fichiers ici.",
    dictRemoveFile: "Supprimer",
    dictFileTooBig: "Ce fichier est tros gros ({{filesize}}mo). Taille max : {{maxFilesize}}mo.",
    dictInvalidFileType: "Ce type de fichier n'est pas autorisé.",
    dictResponseError: "Erreur du serveur {{statusCode}}.",
    dictCancelUpload: "Annuler l'envoi",
    dictCancelUploadConfirmation: "Êtes vous certain·e de vouloir annuler l'envoi ?",
    dictMaxFilesExceeded: "Vous ne pouvez pas envoyer plus de fichiers.",

    init: function() {
      form.addEventListener('submit', function(evt) {
        if (this.getQueuedFiles().length > 0) {
          evt.preventDefault();
          evt.stopPropagation();
          this.processQueue();
        }
      }.bind(this));

      this.on("sendingmultiple", function(data, xhr, formData) {
        // Gets triggered when the form is actually being sent.
        // Hide the success button or the complete form.
      });
      this.on("successmultiple", function(files, response, evt) {
        form.submit();
      });
      this.on("errormultiple", function(files, response, evt) {
        form.submit();
      });
    }
  });
});
