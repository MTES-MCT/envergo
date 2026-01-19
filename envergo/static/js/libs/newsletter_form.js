// This module handles the newsletter opt in form
(function (exports) {
  'use strict';

  var OptinNewsletter = function (formElt) {
    formElt.addEventListener("submit", this.onSubmit.bind(this));
  }
  exports.OptinNewsletter = OptinNewsletter;

  OptinNewsletter.prototype.handleResponse = function (alertDiv, data) {
    if (data.status === "ok") {
      alertDiv.innerHTML = `
        <div class="fr-alert fr-alert--success fr-mb-2w">
          <p>Vous avez reçu un e-mail de confirmation pour valider votre inscription à la newsletter.</p>
        </div>
      `;
    } else {
      let message = '';
      for (const [field, errors] of Object.entries(data.errors)) {
        if (field !== "__all__") {
          errors.forEach(error => {
            message += `<br/>${field} : ${error}`;
          });
        }
      }

      // Handle non-field errors
      if ("__all__" in data.errors) {
        data.errors["__all__"].forEach(error => {
          message += `<br/>${error}`;
        });
      }
      alertDiv.innerHTML = `
        <div class="fr-alert fr-alert--error fr-mb-2w">
          <p>Nous n'avons pas pu enregistrer votre inscription à la newsletter.</p>

          <p>${message}</p>
        </div>
      `;
    }
  }

  OptinNewsletter.prototype.onSubmit = function (event) {
    event.preventDefault(); // Prevent the default form submission

    const form = event.target;
    const formData = new FormData(form);
    const csrfToken = formData.get('csrfmiddlewaretoken');
    const formContainer = form.parentNode;

    // Remove existing alert if it exists
    const existingAlert = document.querySelector("div.newsletter-alert");
    if (existingAlert) {
      formContainer.removeChild(existingAlert);
    }

    const alert = document.createElement('div');
    alert.id = 'newsletter-optin-alert';
    alert.className = "newsletter-alert";
    fetch(form.action, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'Accept': 'application/json',
      },
      body: formData,
    })
      .then(response => {
        return response.json();
      })
      .then(data => {
        this.handleResponse(alert, data);
      })
      .catch(() => {
        alert.innerHTML = `<div class="fr-alert fr-alert--error fr-mb-2w">
          <p>Nous n'avons pas pu enregistrer votre inscription à la newsletter.</p>
        </div>`
      })
      .finally(() => {
        formContainer.insertBefore(alert, formContainer.firstChild);
      });
  };

})(this);

window.addEventListener('load', function () {
  let newsletterForm = document.getElementById('newsletter-optin-form');
  if (newsletterForm) {
    new OptinNewsletter(newsletterForm);
  }
});
