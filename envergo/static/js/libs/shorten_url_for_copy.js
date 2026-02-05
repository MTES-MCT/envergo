(function () {
// a script to shorten the current url before re firing click event for clipboard copy
  const handleClick = e => {
    e.stopImmediatePropagation();
    e.preventDefault();
    const button = e.currentTarget;
    const currentUrl = button.getAttribute("data-clipboard-text") || window.location.href;
    const mapping = new UrlMapping();
    mapping.create(currentUrl).then((json) => {
      button.setAttribute("data-clipboard-text", json.short_url);
    }).catch((error) => {
      console.log("Cannot create url mapping", error);
    }).finally(() => {
      button.removeEventListener("click", handleClick, {capture: true});
      // re-dispatch the click event
      setTimeout(() => {
        button.click();
      }, 0);
    });
  }

  window.addEventListener('load', function () {
    const buttons = document.querySelectorAll(".btn--shorten-url");
    buttons.forEach(button => {
      button.addEventListener("click", handleClick, {capture: true});
    });
  });
})();
