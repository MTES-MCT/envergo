// a script to add actions on the moulinette result banner
(function (exports) {
  'use strict';

  var copyBtn = document.getElementById("copy-btn");
  if (copyBtn) {
    // Put the current Url in the clipboard on click
    // The `navigator.clipboard` API is only available on `https` urls
    if (navigator.clipboard != undefined) {
      copyBtn.addEventListener("click", function () {
        navigator.clipboard.writeText(CURRENT_URL).then(function () {
          var successMessage = document.getElementById('btn-clicked-message');
          successMessage.style.opacity = 1;
          var gif = document.getElementById('btn-clicked-image');
          var src = gif.src;
          gif.src = "";
          gif.src = src; // start the gif animation again

          setTimeout(function () {
            successMessage.style.opacity = 0;
          }, 1000); // Hide after 1 second (1000 ms)
        });
      });
    } else {
      copyBtn.disabled = true;
    }
  }
})(this);
