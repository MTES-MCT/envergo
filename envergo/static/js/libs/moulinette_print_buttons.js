// Handle the "print this page" button
(function (exports, UrlMapping) {
  'use strict';

  const PrintPage = function (shareLinks, printBtns) {
    this.shareLinks = shareLinks;
    this.shareUrl = shareLinks[0].href;
    this.printBtns = printBtns;
    this.mapping = new UrlMapping();
  }
  exports.PrintPage = PrintPage;

  PrintPage.prototype.init = function () {
    this.printBtns.forEach(btn => {
      btn.addEventListener('click', this.onBtnClick.bind(this));
    });
  }

  PrintPage.prototype.onBtnClick = function (evt) {
    this.mapping.create(this.shareUrl)
      .then((json) => {
        this.shareLinks.forEach(link => { link.href = json.short_url; });
      })
      .catch((error) => {
        console.log("Cannot create url mapping", error);
      })
      .finally(() => { window.print() });
  };

})(this, window.UrlMapping);

window.addEventListener('load', function () {
  const shareLinks = document.querySelectorAll('.share-link');
  const printBtns = document.querySelectorAll('.print-btn');
  let printPage = new PrintPage(shareLinks, printBtns);
  printPage.init();
});
