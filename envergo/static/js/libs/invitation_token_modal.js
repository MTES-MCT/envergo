(function (exports) {
      'use strict';

      const InvitationTokenModal = function (modalElt, buttonElt) {
        this.modalElt = modalElt;
        this.buttonElt = buttonElt;

        this.modalError = modalElt.querySelector("#invitation-token-modal-error");
        this.modalLoader = modalElt.querySelector("#invitation-token-modal-loading");
        this.modalContent = modalElt.querySelector("#invitation-token-modal-content");
        this.htmlUrlElt = modalElt.querySelector("#accept-invitation-url");
        this.textUrlElt = modalElt.querySelector("#accept-invitation-url-text");
      };
      exports.InvitationTokenModal = InvitationTokenModal;

      InvitationTokenModal.prototype.init = function () {
        this.buttonElt.addEventListener('click', this.createToken.bind(this));

        const copyButton = this.modalElt.querySelector("#copy-invitation-token-btn");
        // The `navigator.clipboard` API is only available on `https` urls
        if (navigator.clipboard !== undefined) {
          copyButton.addEventListener('click', () => {
            let btnText = copyButton.innerText;

            const htmlEmailBody = this.modalElt.querySelector("#invitation-token-email-html").innerHTML;
            const htmlEmail = `
              <!DOCTYPE html>
              <html lang="fr">
                <head>
                  <meta name="viewport" content="width=device-width">
                  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
                  <title></title>
                </head>
                <body>
                  ${htmlEmailBody}
                </body>
              </html>
              `;
            const textEmail = this.modalElt.querySelector("#invitation-token-email-text").innerText;
            navigator.clipboard.write([
              new ClipboardItem({
                "text/plain": new Blob([textEmail], { type: "text/plain" }),
                "text/html": new Blob([htmlEmail], { type: "text/html" })
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
        const button = document.getElementById('invitation-token-modal-button');
        const invitationTokenModal = new InvitationTokenModal(modal, button);
        invitationTokenModal.init();
      });
    })();
