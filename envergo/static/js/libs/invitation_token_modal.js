(function (exports) {
      'use strict';

      const InvitationTokenModal = function (modalElt, buttonElts) {
        this.modalElt = modalElt;
        this.buttonElts = buttonElts;

        this.modalError = modalElt.querySelector("#invitation-token-modal-error");
        this.modalLoader = modalElt.querySelector("#invitation-token-modal-loading");
        this.modalContent = modalElt.querySelector("#invitation-token-modal-content");
        this.htmlUrlElt = modalElt.querySelector("#accept-invitation-url");
        this.textUrlElt = modalElt.querySelector("#accept-invitation-url-text");
      };
      exports.InvitationTokenModal = InvitationTokenModal;

      InvitationTokenModal.prototype.init = function () {
        this.modalError.style.display = "none"
        this.modalLoader.style.display = "none"
        this.modalContent.style.display = "none"

        for(const buttonElt of this.buttonElts) {
          buttonElt.addEventListener('click', this.createToken.bind(this));
        }

        const copyButtonElts = this.modalElt.querySelectorAll(".copy-invitation-token-btn");

        copyButtonElts.forEach(copyButton => {
          // The `navigator.clipboard` API is only available on `https` urls
          if (navigator.clipboard !== undefined) {
            copyButton.addEventListener('click', () => {
              let btnText = copyButton.innerText;

              const htmlEmail = this.modalElt.querySelector("#invitation-token-email-html").innerHTML;
              const textEmail = this.modalElt.querySelector("#invitation-token-email-text").innerText;
              htmlEmail.replace("Copier le message dans le presse-papier", "")
              navigator.clipboard.write([
                new ClipboardItem({
                  "text/plain": new Blob([textEmail.trim()], { type: "text/plain" }),
                  "text/html": new Blob([htmlEmail.trim()], { type: "text/html" })
                })
              ]).then(() => {
                copyButton.innerText = "Message copié !";
              });

              setTimeout(function () {
                copyButton.innerText = btnText;
              }, 2000);
            });
          } else {
            copyButton.innerText = "Impossible de copier le message";
            copyButton.disabled = true;
          }
        });
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
        this.htmlUrlElt.href = invitation_url
        this.textUrlElt.innerText = invitation_url;
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
        const buttons = document.getElementsByClassName('invitation-token-modal-button');
        const invitationTokenModal = new InvitationTokenModal(modal, buttons);
        invitationTokenModal.init();
      });
    })();
