var _paq = window._paq || [];

/**
 * Make the accordion-organized content analytics friendly.
 *
 * Whenever an accordion section is opened, we push a new state then update
 * stats using matomo.
 *
 * Note : in it's current state, there is no easy way to bind into dsfr's
 * events, so we use MutationObservers to detect whenever a section is
 * opened.
 */
(function (exports) {
  'use strict';

  const AccordionAnalytics = function (accordionElt) {
    this.accordionElt = accordionElt;
    this.currentHash = window.location.hash.substring(1);
    this.init();

    if (this.currentHash) {
      this.openSection(this.currentHash);
    }
  };
  exports.AccordionAnalytics = AccordionAnalytics;

  AccordionAnalytics.prototype.init = function () {
    const collapsibles = this.accordionElt.querySelectorAll('.fr-collapse');
    collapsibles.forEach(this.observeCollapsible.bind(this));
  };

  /**
   * Setup the mutation observers to detect sections opening.
   */
  AccordionAnalytics.prototype.observeCollapsible = function (collapsible) {
    collapsible.addEventListener('dsfr.disclose', this.trackAccordionDisplay.bind(this, collapsible));
    collapsible.addEventListener('dsfr.conceal', this.untrackAccordionDisplay.bind(this));
  };

  AccordionAnalytics.prototype.trackAccordionDisplay = function (collapsible) {
    history.replaceState(null, '', `#${collapsible.id}`);
    _paq.push(['setCustomUrl', window.location.href]);
    _paq.push(['trackPageView']);
  };

  /**
   * Trigger one accordion section's opening
   */
  AccordionAnalytics.prototype.openSection = function (sectionId) {
    let element = document.getElementById(sectionId);
    if (element) {
      dsfr(element).collapse.disclose();
    }
  };

  AccordionAnalytics.prototype.untrackAccordionDisplay = function () {
    history.replaceState(null, '', '#');
  };

})(this);
