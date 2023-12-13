window.addEventListener('load', function () {

  var form = document.getElementById("request-evaluation-form");
  var contactSection = document.getElementById("contact-section");

  var DISPLAY_FIELDS = {
    instructor: ['contact_emails', 'contact_phone', 'project_sponsor_emails', 'project_sponsor_phone_number', 'send_eval_to_sponsor'],
    petitioner: ['project_sponsor_emails', 'project_sponsor_phone_number'],
  };

  var DISPLAY_FIELDSETS = {
    instructor: ['instructor-fieldset', 'petitioner-fieldset'],
    petitioner: ['petitioner-fieldset'],
  }

  var FIELDS_SETUP = {
    instructor: {
      contact_emails: {
        label: 'Adresse(s) e-mail',
      },
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

  var getUserType = function () {
    var input = form.querySelector('[name=user_type]:checked');
    return input.value;
  };

  var toggleContactFields = function (userType) {
    var fieldsToDisplay = DISPLAY_FIELDS[userType];
    var allFieldsDivs = contactSection.querySelectorAll('div[id^=form-group-]')
    allFieldsDivs.forEach(function (fieldDiv) {
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

  var toggleFieldsets = function (userType) {
    var fieldsetsToDisplay = DISPLAY_FIELDSETS[userType];
    var allFieldsets = contactSection.querySelectorAll('fieldset');
    allFieldsets.forEach(function (fieldset) {
      var id = fieldset.id;
      var fieldsetMustBeDisplayed = (fieldsetsToDisplay.indexOf(id) >= 0);
      if (fieldsetMustBeDisplayed) {
        fieldset.classList.remove('fr-hidden');
      } else {
        fieldset.classList.add('fr-hidden');
      }
    });
  };

  var updateFieldLabels = function (userType) {
    var fieldsSetup = FIELDS_SETUP[userType];
    var allFieldsDivs = contactSection.querySelectorAll('div[id^=form-group-]')
    allFieldsDivs.forEach(function (fieldDiv) {
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

  var renderContactSection = function () {
    var userType = getUserType();
    toggleContactFields(userType);
    toggleFieldsets(userType);
    updateFieldLabels(userType);
  };

  form.addEventListener('change', renderContactSection);
  renderContactSection();
});
