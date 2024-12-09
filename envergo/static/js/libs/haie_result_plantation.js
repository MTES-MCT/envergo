window.addEventListener("load", function () {
  let btn = document.getElementById("hedge-input-open-btn");
  let modal = document.getElementById("hedge-input-modal");

  const urlParams = new URLSearchParams(window.location.search);
  const hedgeId = urlParams.get('haies');

  let hedgeIframe;

  // open the hedge input ui in a modal upon the button click
  btn.addEventListener("click", function () {
    let saveUrl = INPUT_HEDGES_URL;
    if (hedgeId) {
      saveUrl += hedgeId + "/";
    }

    saveUrl+= "?mode=plantation";

    hedgeIframe = window.open(saveUrl, "hedge-input-iframe");
    modal.showModal();
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
        window.location.href = "http://haie.local:3000/simulateur/resultat_p/";
    }
  });


});
