document.addEventListener('DOMContentLoaded', function () {
  const readMode = document.getElementById('notes-read-mode');
  const editMode = document.getElementById('notes-edit-mode');
  const editBtnTop = document.getElementById('notes-edit-btn-top');
  const editBtnBottom = document.getElementById('notes-edit-btn-bottom');
  const cancelBtn = document.getElementById('notes-cancel-btn');

  if (!readMode || !editMode) return;

  const showEditMode = () => {
    readMode.style.display = 'none';
    editMode.style.display = '';
  };

  const showReadMode = () => {
    readMode.style.display = '';
    editMode.style.display = 'none';
  };

  editBtnTop.addEventListener('click', showEditMode);
  editBtnBottom.addEventListener('click', showEditMode);
  cancelBtn.addEventListener('click', showReadMode);
});
