(function (exports) {
  'use strict';

  const DemarchesSimplifieesModal = function (modalElt) {
    this.modalElt = modalElt;
    this.formElt =  modalElt.querySelector("#demarche-simplifiee-form");
    this.submitElt = modalElt.querySelector('button[type=submit]');
    this.buttonElts = modalElt.querySelectorAll('input[type="button"], input[type="submit"], button[type=submit]');
    this.closeElt = modalElt.querySelector('.fr-link--close');
  };
  exports.DemarchesSimplifieesModal = DemarchesSimplifieesModal;

  DemarchesSimplifieesModal.prototype.init = function () {
    this.formElt.addEventListener('submit', this.deactivate.bind(this));
    this.formElt.addEventListener('submit', this.submit.bind(this));
  };

  DemarchesSimplifieesModal.prototype.deactivate = function () {
    this.buttonElts.forEach(button => {
      button.disabled = true;
    });

    if (this.closeElt) {
      this.closeElt.disabled = true; // Disable the close button to prevent closing while submitting
    }

    // Escape key prevention
    this.boundPreventEscape = this.preventEscape.bind(this);
    document.addEventListener('keydown', this.boundPreventEscape, true);

    // Prevent clicks outside the modal from closing it
    this.boundPreventClickOutside = this.preventClickOutside.bind(this);
    this.modalElt.addEventListener('click', this.boundPreventClickOutside, true);
  };

  DemarchesSimplifieesModal.prototype.activate = function () {
    this.buttonElts.forEach(button => {
      button.removeAttribute('disabled');
    });

    if (this.closeElt) {
      this.closeElt.removeAttribute('disabled');
    }

    document.removeEventListener('keydown', this.boundPreventEscape, true);
    this.modalElt.removeEventListener('click', this.boundPreventClickOutside, true);
  };

  DemarchesSimplifieesModal.prototype.submit = function (event) {
    event.preventDefault();

    let textElt = document.createElement('span');
    textElt.innerHTML = 'Création en cours…';
    textElt.id = 'demarche-simplifiee-submit-hint';
    textElt.classList.add("fr-hint-text");
    this.submitElt.insertAdjacentElement("afterend", textElt);

    // remove error message if exists
    const errorDiv = document.getElementById('demarche_simplifiee_message');
    if (errorDiv) {
      errorDiv.remove();
    }
    const form = event.target;
    const formData = new FormData(form);
    const newTab = window.open("", '_blank');

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
          // open démarche simplifiée in a new tab and display the read only version of the simulation result
          if (!newTab || newTab.closed || typeof newTab.closed === 'undefined') {
            // if the new tab was blocked by the browser, display the link in the current tab
            displayMessage("Votre navigateur empêche l'ouverture d'un nouvel onglet.",
              `Veuillez cliquer sur <a href="${data.demarche_simplifiee_url}">ce lien</a> pour commencer votre démarche.`,
              "info");
          } else {
            newTab.location = data.demarche_simplifiee_url;
            window.location.href = data.read_only_url;
          }
        } else {
          throw data;
        }
      })
      .catch(error => {
        if (newTab) {
          // close the new tab if it was opened
          newTab.close();
        }

        displayMessage(error.error_title || 'Nous avons rencontré un problème',
          error.error_body || "Merci de réessayer ultérieurement.",
          "error");
      })
      .finally(() => {
        this.activate();
        let textElt = document.getElementById('demarche-simplifiee-submit-hint');
        if (textElt) {
          textElt.remove();
        }
        // close the modal
        if (this.modalElt) {
          dsfr(this.modalElt).modal.conceal();
        }
      });
  };

  DemarchesSimplifieesModal.prototype.preventEscape = function (event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }

  DemarchesSimplifieesModal.prototype.preventClickOutside = function (event) {
    const body = this.modalElt.querySelector('.fr-modal__body');
      if (!body.contains(event.target)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
  }

})(this);


function displayMessage(title, message, type) {
  const projectResultTopBar = document.getElementById('project-result-top-bar');
  const notification = `
                          <div id="demarche_simplifiee_message" class="messages fr-p-5w">
                            <div class="fr-alert fr-alert--${type} fr-alert--sm">
                              <h3 class="fr-alert__title">${title}</h3>
                              <p>${message}</p>
                            </div>
                          </div>
                        `;
  projectResultTopBar.insertAdjacentHTML('afterbegin', notification);
  // Scroll smoothly to the message
  projectResultTopBar.scrollIntoView({behavior: 'smooth'});
}

(function () {
// a script to add actions on the moulinette result banner
  window.addEventListener('load', function () {
    const modal = document.getElementById('demarches-simplifiees-modal');
    const demarchesSimplifieesModal = new DemarchesSimplifieesModal(modal);
    demarchesSimplifieesModal.init();
  });
})();
