// Description: This script is used to see the title of an accordion when the page is loaded with a hash in the URL.

window.addEventListener('load', function() {
  const id = window.location.hash.slice(1);
  if (id) {
    const accordionButton = document.getElementById(id);
    if (accordionButton &&  accordionButton.classList.contains('fr-accordion__btn')) {
      accordionButton.click();
    }
  }
});
