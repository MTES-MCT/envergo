/**
 * Handle the invitation tokens.
 *  - Invitation modal "Invite new user"
 *  - "Revoke access" buttons
 *
 * We need to fetch a new invitation token everytime the user clicks on the
 * "Générer le message et le lien d'accès" because each token is only valid once.
 */

(function (exports) {
  'use strict';

  const InvitationTokenConsultations = function () {
    this.modal = document.getElementById('invitation-token-modal');
    this.generateBtn = document.getElementById('generate-invitation-btn');
    this.revokeModal = document.getElementById('revoke-token-modal');
    this.revokeForms = document.querySelectorAll('.revoke-token-form');

    if (this.modal) {
      this.modalLoader = this.modal.querySelector("#invitation-token-modal-loading");
      this.modalError = this.modal.querySelector("#invitation-token-modal-error");
      this.modalContent = this.modal.querySelector("#invitation-token-modal-content");
    }
  };

  exports.InvitationTokenConsultations = InvitationTokenConsultations;

  InvitationTokenConsultations.prototype.init = function () {
    if (this.modal) {
      this.modalLoader.style.display = "none";
      this.modalError.style.display = "none";
      this.modalContent.style.display = "none";
    }

    // Generate token button
    if (this.generateBtn) {
      this.generateBtn.addEventListener('click', this.generateToken.bind(this));
    }

    // Intercept revoke form submissions for progressive enhancement
    this.revokeForms.forEach(form => {
      form.addEventListener('submit', (e) => {
        e.preventDefault(); // Prevent direct submission

        // Copy the token_id to the modal form
        const tokenId = form.querySelector('input[name="token_id"]').value;
        const modalInput = document.getElementById('revoke-token-modal-id');
        if (modalInput) {
          modalInput.value = tokenId;
        }

        // Open the modal using DSFR API
        if (this.revokeModal && window.dsfr) {
          window.dsfr(this.revokeModal).modal.disclose();
        }
      });
    });
  };

  InvitationTokenConsultations.prototype.generateToken = function () {
    // Save original button state
    const originalText = this.generateBtn.textContent;
    const originalClasses = this.generateBtn.className;

    // Update button to loading state
    this.generateBtn.disabled = true;
    this.generateBtn.classList.remove('fr-icon-user-add-line');
    this.generateBtn.classList.add('spinner');
    this.generateBtn.classList.add('fr-icon-settings-5-line');
    this.generateBtn.textContent = "Génération de l'invitation…";

    // Minimum delay of 2 seconds
    const minDelayPromise = new Promise(resolve => setTimeout(resolve, 2000));

    // Fetch content
    const fetchPromise = fetch(INVITATION_TOKEN_CREATE_URL, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': CSRF_TOKEN,
      },
    })
      .then(response => {
        if (!response.ok) {
          throw new Error('Network error, token creation failed');
        }
        return response.text();
      });

    // Wait for both the fetch and the minimum delay
    // We add a minimal waiting delay to make it clear that we are
    // doing hard an important work™
    Promise.all([fetchPromise, minDelayPromise])
      .then(([html]) => {
        this.restoreButton(originalText, originalClasses);
        this.displayTokenModal(html);
      })
      .catch(error => {
        console.error('Error creating invitation token:', error);
        this.restoreButton(originalText, originalClasses);
        this.displayError();
      });
  };

  InvitationTokenConsultations.prototype.restoreButton = function (originalText, originalClasses) {
    this.generateBtn.disabled = false;
    this.generateBtn.className = originalClasses;
    this.generateBtn.textContent = originalText;
  };

  InvitationTokenConsultations.prototype.displayTokenModal = function (html) {
    this.modalLoader.style.display = "none";
    this.modalError.style.display = "none";
    this.modalContent.innerHTML = html;
    this.modalContent.style.display = "inherit";

    // Open modal via DSFR API
    if (this.modal && window.dsfr) {
      window.dsfr(this.modal).modal.disclose();
    }

    // Set up copy button
    const copyButton = this.modalContent.querySelector("#copy-invitation-token-btn");
    if (copyButton && navigator.clipboard !== undefined) {
      copyButton.addEventListener('click', () => {
        const htmlEmail = this.modalContent.querySelector("#invitation-token-email-html").innerHTML;
        const textEmail = this.modalContent.querySelector("#invitation-token-email-text").innerText;

        navigator.clipboard.write([
          new ClipboardItem({
            "text/plain": new Blob([textEmail.trim()], { type: "text/plain" }),
            "text/html": new Blob([htmlEmail.trim()], { type: "text/html" })
          })
        ]).then(() => {
          // Close modal immediately after copy
          const closeButton = this.modal.querySelector('.fr-link--close');
          if (closeButton) {
            closeButton.click();
          }

          // Show success message
          this.showSuccessMessage();
        });
      });
    } else if (copyButton) {
      copyButton.innerText = "Impossible de copier le message";
      copyButton.disabled = true;
    }
  };

  InvitationTokenConsultations.prototype.showSuccessMessage = function () {
    const container = document.getElementById('copy-success-message-container');
    if (!container) return;

    // Create success message
    const alertDiv = document.createElement('div');
    alertDiv.className = 'fr-alert fr-alert--success fr-mb-3w';
    alertDiv.innerHTML = `
      <p>Le message a été copié</p>
    `;

    // Insert message
    container.innerHTML = '';
    container.appendChild(alertDiv);

    // Remove message after 5 seconds
    setTimeout(() => {
      alertDiv.style.transition = 'opacity 0.5s';
      alertDiv.style.opacity = '0';
      setTimeout(() => {
        container.innerHTML = '';
      }, 500);
    }, 5000);
  };

  InvitationTokenConsultations.prototype.displayError = function () {
    this.modalLoader.style.display = "none";
    this.modalError.style.display = "inherit";
    this.modalContent.style.display = "none";

    // Open modal via DSFR API
    if (this.modal && window.dsfr) {
      window.dsfr(this.modal).modal.disclose();
    }
  };

})(this);

(function () {
  window.addEventListener('load', function () {
    const consultations = new InvitationTokenConsultations();
    consultations.init();
  });
})();
