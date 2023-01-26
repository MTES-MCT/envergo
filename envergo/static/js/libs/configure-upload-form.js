window.addEventListener('load', function() {

  var form = document.getElementById(DROPZONE_FORM);
  var field = document.getElementById(DROPZONE_FIELD);
  var submitBtn = form.querySelector('button[type=submit]');
  var btnIcon = submitBtn.querySelector('span[class^="fr-fi-"]');
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
    autoProcessQueue: true,
    uploadMultiple: true,
    parallelUploads: 100,
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

      // Disable the form while files are being uploaded
      this.on("addedfiles", function(files) {
        this.disableForm();
      }.bind(this));

      // Re-enable the form when all files have been uploaded
      this.on("queuecomplete", function(files, response, evt) {
        this.enableForm();
      }.bind(this));

      // Make sure the form cannot be submitted while files are being uploaded
      form.addEventListener('submit', function(evt) {
        if (this.getQueuedFiles().length > 0) {
          evt.preventDefault();
          evt.stopPropagation();
        }
      }.bind(this));

      this.on("removedfile", function(file) {}.bind(this));
    }
  });

  // Disable the confirmation form while files are being uploaded
  Dropzone.prototype.disableForm = function() {
    // Disable form submit
    submitBtn.setAttribute("disabled", "");

    // Update button message
    btnIcon.classList.remove("fr-fi-checkbox-circle-line");
    btnIcon.classList.add("fr-fi-refresh-line");
    btnIcon.classList.add("spinner");
    btnIcon.textContent = "Veuillez patienter pendant le chargement de vos fichiers";
    btnIcon.setAttribute("role", "alert");
  };

  // Reactivate the confirmation form
  Dropzone.prototype.enableForm = function() {
    submitBtn.removeAttribute("disabled");

    // Update button message
    btnIcon.classList.add("fr-fi-checkbox-circle-line");
    btnIcon.classList.remove("fr-fi-refresh-line");
    btnIcon.classList.remove("spinner");
    btnIcon.textContent = "Envoyer votre demande d'évaluation";
    btnIcon.removeAttribute("role");
  };
});
