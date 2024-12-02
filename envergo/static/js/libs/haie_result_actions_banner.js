function displayMessage(title, message, type) {
  const projectResult = document.getElementById('project-result');
  const notification = `
                          <div id="demarche_simplifiee_message" class="messages fr-p-5w">
                            <div class="fr-alert fr-alert--${type} fr-alert--sm">
                              <h3 class="fr-alert__title">${title}</h3>
                              <p>${message}</p>
                            </div>
                          </div>
                        `;
  projectResult.insertAdjacentHTML('afterbegin', notification);
  // Scroll smoothly to the message
  projectResult.scrollIntoView({behavior: 'smooth'});
}

// a script to add actions on the moulinette result banner
window.addEventListener('load', function () {
  (function (exports) {
    'use strict';

    var demarcheForm = document.getElementById("demarche-simplifiee-form");
    if (demarcheForm) {

      demarcheForm.addEventListener("submit", function (event) {
        event.preventDefault();

        // Replace form button by a loader
        const submitButton = document.getElementById("demarche-simplifiee-banner-btn");
        let originalButton = null;
        const textNode = document.createTextNode('Redirection vers Démarches simplifiées…');
        if (submitButton) {
          originalButton = submitButton.cloneNode(true);
          submitButton.parentNode.replaceChild(textNode, submitButton);
        }

        // remove error message if exists
        const errorDiv = document.getElementById('demarche_simplifiee_message');
        if (errorDiv) {
          errorDiv.remove();
        }
        const form = event.target;
        const formData = new FormData(form);

        fetch(form.action, {
          method: 'POST',
          body: formData,
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          },
        })
          .then(response => response.json())
          .then(data => {
            if (data.demarche_simplifiee_url && data.read_only_url) {
              // open démarche simplifiée in a new tab and display the read only version of the simuation result
              const newTab = window.open(data.demarche_simplifiee_url, '_blank');
              if (!newTab || newTab.closed || typeof newTab.closed === 'undefined') {
                // if the new tab was blocked by the browser, display the link in the current tab
                displayMessage("Votre navigateur empêche l'ouverture d'un nouvel onglet.",
                  `Veuillez cliquer sur <a href="${data.demarche_simplifiee_url}">ce lien</a> pour commencer votre démarche.`,
                  "info");
              } else {
                window.location.href = data.read_only_url;
              }
            } else {
              throw data;
            }
          })
          .catch(error => {
            displayMessage(error.error_title || 'Nous avons rencontré un problème',
                  error.error_body || "Merci de réessayer ultérieurement.",
                  "error");
          })
          .finally(() => {
            // Replace loader by original button
            if (originalButton) {
              textNode.parentNode.replaceChild(originalButton, textNode);
            }
          });
      });

      // There is multiples buttons that can submit the form across the result page
      const submitButtons = document.querySelectorAll('.demarche-simplifiee-btn');
      submitButtons.forEach(function (button) {
        button.addEventListener('click', function (event) {
          event.preventDefault();
          var submitEvent = new Event('submit', { bubbles: true, cancelable: true });
          demarcheForm.dispatchEvent(submitEvent);
        });
      });
    }
  })(this);
});
