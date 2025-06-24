// Confirmation message for instruction form
document.addEventListener('DOMContentLoaded', function () {
  var forms = document.querySelectorAll('form');
  var beforeUnloadListenerAdded = false;

  function preventLeaving(e) {
    e.preventDefault();
    var confirmationMessage = 'Vous avez des modifications non enregistrées. Êtes-vous sûr de vouloir quitter la page ?';
    e.returnValue = confirmationMessage; // Standard for most browsers
    return confirmationMessage; // For some older browsers
  }

  forms.forEach(function (form) {
    form.addEventListener('change', function () {
      if (!beforeUnloadListenerAdded) {
        window.addEventListener('beforeunload', preventLeaving);
        beforeUnloadListenerAdded = true;
      }
    });

    form.addEventListener('submit', function () {
      if(beforeUnloadListenerAdded){
        window.removeEventListener('beforeunload', preventLeaving);
        beforeUnloadListenerAdded = false;
      }
    });
  });
});
