window.addEventListener('load', function () {

  var form = document.getElementById("request-evaluation-form");
  var contactSection = document.getElementById("contact-section");

  var FIELDS_SETUP = {
    instructor: {
      contact_emails: {
        label: 'Adresse(s) e-mail',
      },
      project_sponsor_emails: {
        label: 'Adresse(s) e-mail',
        help_text: "Pétitionnaire, maître d'œuvre…",
      },
      project_sponsor_phone_number: {
        label: "Téléphone du porteur de projet",
      }
    },
    petitioner: {
      project_sponsor_emails: {
        label: "Adresse(s) e-mail",
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

  var getSendEval = function () {
    var checkbox = form.querySelector('[name=send_eval_to_sponsor]');
    return checkbox.checked;
  };

  var updateForm = function (userType, sendEval) {
    form.dataset.userType = userType;
    form.dataset.sendEval = sendEval;
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
    var sendEval = getSendEval();
    updateForm(userType, sendEval);
    updateFieldLabels(userType);
  };

  form.addEventListener('change', renderContactSection);
  renderContactSection();
});
