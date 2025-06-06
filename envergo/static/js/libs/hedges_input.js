window.addEventListener("load", function () {
  let hedgeIframe;
  let buttons = document.querySelectorAll(".hedge-input-open-btn");
  let modal = document.getElementById("hedge-input-modal");

  const openModal = function () {
    let saveUrl = new URL(HEDGES_PLANTATION_URL);
    if (typeof SOURCE_PAGE !== 'undefined') {
      saveUrl.searchParams.set("source_page", SOURCE_PAGE);
    }

    modal.showModal();

    hedgeIframe = document.createElement("iframe");
    hedgeIframe.id = "hedge-input-iframe";
    hedgeIframe.width = "100%";
    hedgeIframe.height = "100%";
    hedgeIframe.allowFullscreen = true;
    hedgeIframe.src = saveUrl;
    hedgeIframe.addEventListener("load", function () {
      modal.classList.add("loaded");
    });
    // Start iframe loading
    modal.appendChild(hedgeIframe);
  }

  if (window.location.hash === '#plantation') {
    openModal();
  }

  // open the hedge input ui in a modal upon the button click
  buttons.forEach(button => {
    button.addEventListener("click", function () {
      openModal();
    });
  });

  // When the input is saved, close the modal
  window.addEventListener("message", function (event) {
    if (event.origin !== window.location.origin) {
      return;
    }

    if (event.data.action === "cancel") {
      modal.close();
      hedgeIframe.remove();
      modal.classList.remove("loaded");
    }

    if (event.data.input_id) {
      const query = new URLSearchParams(window.location.search);
      query.set("haies", event.data.input_id);
      window.location.href = `${RESULT_P_URL}?${query.toString()}`;
    }
  });
});
