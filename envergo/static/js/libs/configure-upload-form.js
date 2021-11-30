window.addEventListener('load', function() {
  let dropzone = new Dropzone('form#upload-form', {
    url: '/',
    paramName: 'files',
    maxFilesize: 20,
    maxFiles: 10,
    acceptedFiles: 'image/*,application/pdf,application/zip',
    autoProcessQueue: false,
    uploadMultiple: true,
    parallelUploads: 100,
    maxFiles: 100
  });
});
