window.addEventListener("load", function () {
  let buttons = document.querySelectorAll(".hedge-input-open-btn");
  let modal = document.getElementById("hedge-input-modal");

  const urlParams = new URLSearchParams(window.location.search);
  const hedgeId = urlParams.get('haies');

  let hedgeIframe;

  const openModal = function () {
    let saveUrl = HEDGES_PLANTATION_URL;
    if (hedgeId) {
      saveUrl += hedgeId + "/";
    }

    hedgeIframe = window.open(saveUrl, "hedge-input-iframe");
    modal.showModal();
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
      hedgeIframe.close();
      modal.close();
    }

    if (event.data.input_id) {
      const query = new URLSearchParams(window.location.search);
      query.set("haies", event.data.input_id);
      window.location.href = `${RESULT_P_URL}?${query.toString()}`;
    }
  });


});