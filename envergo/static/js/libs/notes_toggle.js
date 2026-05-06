document.addEventListener('DOMContentLoaded', function () {
  const readMode = document.getElementById('notes-read-mode');
  const editMode = document.getElementById('notes-edit-mode');
  const editBtnTop = document.getElementById('notes-edit-btn-top');
  const editBtnBottom = document.getElementById('notes-edit-btn-bottom');
  const bottomContainer = document.getElementById('notes-edit-btn-bottom-container');
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

  const checkBottomButton = () => {
    const rect = editBtnTop.getBoundingClientRect();
    const visible = rect.bottom > 0 && rect.top < window.innerHeight;
    bottomContainer.style.display = visible ? 'none' : '';
  };

  editBtnTop.addEventListener('click', showEditMode);
  editBtnBottom.addEventListener('click', showEditMode);
  cancelBtn.addEventListener('click', showReadMode);

  window.addEventListener('scroll', checkBottomButton);
  window.addEventListener('resize', checkBottomButton);
  checkBottomButton();
});
