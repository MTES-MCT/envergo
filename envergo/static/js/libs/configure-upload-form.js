window.addEventListener('load', function() {

  var form = document.getElementById(DROPZONE_FORM);
  var field = document.getElementById(DROPZONE_FIELD);
  var previewElt = document.getElementById('dropzone-previews');
  var uploadedData = JSON.parse(document.getElementById('uploaded-files').textContent);

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

    dictDefaultMessage: "Cliquez ou glissez-déposez vos fichiers ici.",
    dictRemoveFile: "Supprimer",
    dictFileTooBig: "Ce fichier est tros gros ({{filesize}}mo). Taille max : {{maxFilesize}}mo.",
    dictInvalidFileType: "Ce type de fichier n'est pas autorisé.",
    dictResponseError: "Erreur du serveur {{statusCode}}.",
    dictCancelUpload: "Annuler l'envoi",
    dictCancelUploadConfirmation: "Êtes vous certain·e de vouloir annuler l'envoi ?",
    dictMaxFilesExceeded: "Vous ne pouvez pas envoyer plus de fichiers.",

    init: function() {

      // Process the upload queue before submiting the form
      form.addEventListener('submit', function(evt) {
        if (this.getQueuedFiles().length > 0) {
          evt.preventDefault();
          evt.stopPropagation();
          this.processQueue();
        }
      }.bind(this));

      // Display previously uploaded files in the upload preview
      uploadedData.forEach(function(data) {
        this.options.addedfile.call(this, data);
      }.bind(this));


      // Whatever happens with the upload, we need to submit the form
      // to display success or error validation
      this.on("successmultiple", function(files, response, evt) {
        form.submit();
      });
    }
  });
});
