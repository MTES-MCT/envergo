window.addEventListener('load', function() {

  var form = document.getElementById(FORM_ID);
  var contactSection = document.getElementById(CONTACT_SECTION_ID);

  var DISPLAY_FIELDS = {
    instructor: ['contact_email', 'project_sponsor_emails', 'project_sponsor_phone_number', 'send_eval_to_sponsor'],
    petitioner: ['project_sponsor_emails', 'project_sponsor_phone_number'],
  };

  var FIELDS_SETUP = {
    instructor: {
      project_sponsor_emails: {
        label: 'Adresse(s) e-mail du porteur de projet',
        help_text: "Pétitionnaire, maître d'œuvre…",
      },
      project_sponsor_phone_number: {
        label: "Téléphone du porteur de projet",
      }

    },
    petitioner: {
      project_sponsor_emails: {
        label: "Adresse(s) e-mail à qui adresser l'évaluation",
        help_text: "Porteur de projet, maître d'œuvre…",
      },
      project_sponsor_phone_number: {
        label: "Contact téléphonique",
      }
    }
  };

  var getUserType = function() {
    var input = form.querySelector('[name=user_type]:checked');
    return input.value;
  };

  var toggleContactFields = function(userType) {
    var fieldsToDisplay = DISPLAY_FIELDS[userType];
    var allFieldsDivs = contactSection.querySelectorAll('div[id^=form-group-]')
    allFieldsDivs.forEach(function(fieldDiv) {
      var divId = fieldDiv.id;
      var fieldName = divId.replace('form-group-', '');
      var fieldMustBeDisplayed = (fieldsToDisplay.indexOf(fieldName) >= 0);
      if (fieldMustBeDisplayed) {
        fieldDiv.classList.remove('fr-hidden');
      } else {
        fieldDiv.classList.add('fr-hidden');
      }
    });
  };

  var updateFieldLabels = function(userType) {
    var fieldsSetup = FIELDS_SETUP[userType];
    var allFieldsDivs = contactSection.querySelectorAll('div[id^=form-group-]')
    allFieldsDivs.forEach(function(fieldDiv) {
      var divId = fieldDiv.id;
      var fieldName = divId.replace('form-group-', '');
      var setup = fieldsSetup[fieldName];
      if (setup) {
        var label = fieldDiv.querySelector('span.label-content');
        label.innerHTML = setup.label;

        if (setup.help_text) {
          var help = fieldDiv.querySelector('span.fr-hint-text');
          help.innerHTML = setup.help_text;
        }
      }
    });
  };

  var renderContactSection = function() {
    var userType = getUserType();
    toggleContactFields(userType);
    updateFieldLabels(userType);
  };

  form.addEventListener('change', renderContactSection);
  renderContactSection();
});
