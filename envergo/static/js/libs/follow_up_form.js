// JavaScript to handle follow/unfollow actions via AJAX. The form submission should also work without JavaScript.
window.addEventListener('load', function () {

  document.querySelectorAll(".follow-up-form").forEach(form => {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const formData = new FormData(form);

      const button = form.querySelector("button");
      button.disabled = true;
      fetch(form.action, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      }).then(response => {
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        // Update the button based on follow status
        if (formData.get("follow") === "true") {
          form.querySelector('input[name="follow"]').value = "false";
          button.classList.remove("fr-icon-star-line");
          button.classList.add("fr-icon-star-fill");
          button.textContent = "Ne plus suivre";
        } else {
          form.querySelector('input[name="follow"]').value = "true";
          button.classList.remove("fr-icon-star-fill");
          button.classList.add("fr-icon-star-line");
          button.textContent = "Suivre";
        }
      }).catch(error => {
        console.error("Error:", error);
      }).finally(() => {
        button.disabled = false;
      });
    });
  });
});
