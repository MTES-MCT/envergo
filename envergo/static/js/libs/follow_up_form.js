/**
 * Handles follow/unfollow toggle via AJAX on the dossier list.
 * Falls back to a normal form POST when JS is unavailable.
 *
 * Exposes FollowUpForm.init(container) so it can be called after
 * dynamic content insertion (e.g. htmx swaps).
 */
(function (exports) {
  "use strict";

  class FollowUpForm {
    constructor(form) {
      this.form = form;
      this.button = form.querySelector("button");
      this.followInput = form.querySelector('input[name="follow"]');
    }

    bind() {
      this.form.addEventListener("submit", (e) => {
        e.preventDefault();
        this.toggle();
      });
    }

    toggle() {
      this.button.disabled = true;
      var formData = new FormData(this.form);

      fetch(this.form.action, {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      })
        .then((response) => {
          if (!response.ok) throw new Error("Network response was not ok");

          var isFollowing = formData.get("follow") === "true";
          this.followInput.value = isFollowing ? "false" : "true";
          this.button.classList.replace(
            isFollowing ? "fr-icon-star-line" : "fr-icon-star-fill",
            isFollowing ? "fr-icon-star-fill" : "fr-icon-star-line"
          );
          this.button.textContent = isFollowing ? "Ne plus suivre" : "Suivre";
        })
        .catch((error) => {
          console.error("Follow toggle error:", error);
        })
        .finally(() => {
          this.button.disabled = false;
        });
    }

    static init(container) {
      container.querySelectorAll(".follow-up-form").forEach(function (form) {
        if (form._followUpBound) return;
        form._followUpBound = true;
        new FollowUpForm(form).bind();
      });
    }
  }

  exports.FollowUpForm = FollowUpForm;
})(this);

window.addEventListener("load", function () {
  FollowUpForm.init(document);
});
