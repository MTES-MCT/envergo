window.addEventListener("load", function () {
  let buttons = document.querySelectorAll(".hedge-input-open-btn");
  let modal = document.getElementById("hedge-input-modal");

  const urlParams = new URLSearchParams(window.location.search);
  const hedgeId = urlParams.get('haies');

  const query = new URLSearchParams(window.location.search);

  let hedgeIframe;

  const openModal = function () {
    query.delete('edit_plantation');
    let saveUrl = INPUT_HEDGES_URL;
    if (hedgeId) {
      saveUrl += hedgeId + "/";
    }

    saveUrl += "?mode=plantation";

    hedgeIframe = window.open(saveUrl, "hedge-input-iframe");
    modal.showModal();
  }

  if (query.get('edit_plantation')) {
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
      query.set("haies", event.data.input_id);
      window.location.href = `${RESULT_P_URL}?${query.toString()}`;
    }
  });


});
