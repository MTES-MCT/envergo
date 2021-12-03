window.addEventListener('load', function() {

  var form = document.getElementById(DROPZONE_FORM);
  var field = document.getElementById(DROPZONE_FIELD);
  var previewElt = document.getElementById('dropzone-previews');
  previewElt.classList.add('dropzone');

  var dropzone = new Dropzone(form, {
    url: form.action,
    paramName: 'additional_files',
    maxFilesize: 20,
    maxFiles: 10,
    acceptedFiles: 'image/*,application/pdf,application/zip',
    autoProcessQueue: false,
    uploadMultiple: true,
    parallelUploads: 100,
    maxFiles: 100,
    addRemoveLinks: true,
    previewsContainer: '.dropzone-previews',
    init: function() {
      form.addEventListener('submit', function(evt) {
        evt.preventDefault();
        evt.stopPropagation();
        this.processQueue();
      }.bind(this));
    }
  });
});
