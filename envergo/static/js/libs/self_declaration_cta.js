// Dismiss the self declaration block for 48 hours

window.addEventListener('load', function () {
  const key = "self-declaration-cta-dismissed";
  const el = document.getElementById("self-declaration-cta-v2");
  if(!el){
    return
  }
  const dismissed = localStorage.getItem(key);
  if (dismissed && Date.now() - parseInt(dismissed) < 48 * 3600 * 1000) {
    el.style.display = "none";
  }
  document
    .getElementById("self-declaration-cta-close-btn")
    .addEventListener("click", function () {
      el.style.display = "none";
      localStorage.setItem(key, Date.now().toString());

      _paq.push(["trackEvent", "Evaluation", "HideSelfDeclareClick"]);
    });
});
