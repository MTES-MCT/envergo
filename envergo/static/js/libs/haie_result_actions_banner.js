// a script to add actions on the moulinette result banner
(function (exports) {
    'use strict';

    var demarcheForm = document.getElementById("demarche-simplifiee-form");
    if (demarcheForm) {

        demarcheForm.addEventListener("submit", function (event) {
            event.preventDefault();

            // Replace form button by a loader
            const submitButton = document.getElementById("demarche-simplifiee-btn");
            let originalButton = null;
            const textNode = document.createTextNode('Redirection vers Démarches simplifiées...');
            if (submitButton) {
                originalButton = submitButton.cloneNode(true);
                submitButton.parentNode.replaceChild(textNode, submitButton);
            }

            // remove error message if exists
            const errorDiv = document.getElementById('demarche_simplifiee_error');
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
                        window.open(data.demarche_simplifiee_url, '_blank');
                        window.location.href = data.read_only_url;
                    } else {
                      // display an error message
                        const projectResult = document.getElementById('project-result');
                        const errorMessage = `
                          <div id="demarche_simplifiee_error" class="messages fr-p-5w">
                            <div class="fr-alert fr-alert--error fr-alert--sm">
                              <h3 class="fr-alert__title">${data.error_title || 'Nous avons rencontré un problème'}</h3>
                              <p>${data.error_body || "Merci de réessayer ultérieurement."}</p>
                            </div>
                          </div>
                        `;
                        projectResult.insertAdjacentHTML('afterbegin', errorMessage);
                        // Scroll smoothly to the error message
                        projectResult.scrollIntoView({ behavior: 'smooth' });
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                })
                .finally(() => {
                    // Replace loader by original button
                    if (originalButton) {
                        textNode.parentNode.replaceChild(originalButton, textNode);
                    }
                });
        });
    }
})(this);
