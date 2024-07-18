(function (exports) {
  'use strict';

  document.getElementById("copy-btn").addEventListener("click", function () {
    navigator.clipboard.writeText(SHARING_URL).then(function () {
      var successMessage = document.getElementById('btn-clicked-message');
      successMessage.style.opacity = 1;
      var gif = document.getElementById('btn-clicked-image');
      var src = gif.src;
      gif.src = "";
      gif.src = src; // start the gif animation again

      setTimeout(function() {
          successMessage.style.opacity = 0;
      }, 1000); // Hide after 1 second (1000 ms)
      });
  });
})(this);
