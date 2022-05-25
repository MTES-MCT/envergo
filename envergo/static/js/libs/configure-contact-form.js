window.addEventListener('load', function() {

  var form = document.getElementById(FORM_ID);
  var contactSection = document.getElementById(CONTACT_SECTION_ID);

  var DISPLAY_FIELDS = {
    'instructor': ['contact_email', 'project_sponsor_emails', 'project_sponsor_phone_number', 'send_eval_to_sponsor'],
    'petitioner': ['project_sponsor_emails', 'project_sponsor_phone_number'],
  };

  var getUserType = function() {
    var input = form.querySelector('[name=user_type]:checked');
    return input.value;
  };

  var toggleContactFields = function(userType) {
    var fieldsToDisplay = DISPLAY_FIELDS[userType];
    var allFieldsDivs = contactSection.querySelectorAll('div[id^=form-group-]')
    allFieldsDivs.forEach(function(fieldDiv) {
      var dievId = fieldDiv.id;
      var fieldName = dievId.replace('form-group-', '');
      var fieldMustBeDisplayed = (fieldsToDisplay.indexOf(fieldName) >= 0);
      if (fieldMustBeDisplayed) {
        fieldDiv.classList.remove('fr-hidden');
      } else {
        fieldDiv.classList.add('fr-hidden');
      }
    });
  };

  var updateFieldLabels = function(userType) {};

  var renderContactSection = function() {
    var userType = getUserType();
    toggleContactFields(userType);
    updateFieldLabels(userType);
  };

  form.addEventListener('change', renderContactSection);
  renderContactSection();
});
