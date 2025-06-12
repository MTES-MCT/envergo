(function (exports) {
      'use strict';

      const InvitationTokenModal = function (modalElt, buttonElt) {
        this.modalElt = modalElt;
        this.buttonElt = buttonElt;

        this.modalError = modalElt.querySelector("#invitation-token-modal-error");
        this.modalLoader = modalElt.querySelector("#invitation-token-modal-loading");
        this.modalContent = modalElt.querySelector("#invitation-token-modal-content");
        this.urlElt = modalElt.querySelector("#invitation-token-modal-url");
      };
      exports.InvitationTokenModal = InvitationTokenModal;

      InvitationTokenModal.prototype.init = function () {
        this.buttonElt.addEventListener('click', this.createToken.bind(this));
      };

      InvitationTokenModal.prototype.createToken = function () {
        this.modalError.style.display = "none"
        this.modalLoader.style.display = "inherit"
        this.modalContent.style.display = "none"

        fetch(INVITATION_TOKEN_URL, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': CSRF_TOKEN,
          },
        })
          .then(response => response.json())
          .then(data => {
            if (data.invitation_url) {
              this.displayToken(data.invitation_url)
            } else {
              throw data;
            }
          })
          .catch(error => {
            console.error('Error creating invitation token:', error);
            this.displayError();
          });
      };

      InvitationTokenModal.prototype.displayToken = function (invitation_url) {
        this.modalError.style.display = "none"
        this.modalLoader.style.display = "none"
        this.modalContent.style.display = "inherit"
        this.urlElt.innerHTML = invitation_url
      };

      InvitationTokenModal.prototype.displayError = function () {
        this.modalError.style.display = "inherit"
        this.modalLoader.style.display = "none"
        this.modalContent.style.display = "none"
      };

    })(this);

    (function () {
      window.addEventListener('load', function () {
        const modal = document.getElementById('invitation-token-modal');
        const button = document.getElementById('invitation-token-modal-button');
        const invitationTokenModal = new InvitationTokenModal(modal, button);
        invitationTokenModal.init();
      });
    })();
