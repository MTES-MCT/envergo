window.addEventListener('load', function () {

  initDropzoneUpload({
    formId: DROPZONE_FORM,
    uploadUrl: DROPZONE_UPLOAD_URL,
    maxFiles: DROPZONE_MAX_FILES,
    maxFilesize: DROPZONE_MAX_FILESIZE,
    paramName: 'map_files',
    acceptedFiles: '.gpkg,.zip',
    dictInvalidFileType: "Ce type de fichier n'est pas autorisé (.gpkg ou .zip attendu).",
    timeout: 0,
  });
});
