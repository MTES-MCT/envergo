/**
 * Make the accordion-organized content analytics friendly.
 *
 * Whenever an accordion section is opened, we push a new state then update
 * stats using matomo.
 *
 * Note : in its current state, there is no easy way to bind into dsfr's
 * events, so we use MutationObservers to detect whenever a section is
 * opened.
 */
(function (exports) {
  'use strict';

  const AccordionAnalytics = function (accordionElt) {
    this.accordionElt = accordionElt;
    this.currentHash = window.location.hash.substring(1);

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
    collapsible.addEventListener('dsfr.conceal', this.untrackAccordionDisplay.bind(this, collapsible));
  };

  AccordionAnalytics.prototype.trackAccordionDisplay = function (collapsible) {
    history.replaceState(null, '', `#${collapsible.id}`);
    _paq.push(['setCustomUrl', window.location.href]);
    _paq.push(['trackPageView']);
  };

  /**
   * Trigger one accordion section's opening.
   */
  AccordionAnalytics.prototype.openSection = function (sectionId, retries = 10) {
    let element = document.getElementById(sectionId);
    if (!element) return;

    let dsfrElement = dsfr(element);
    if (dsfrElement && dsfrElement.collapse) {
      dsfrElement.collapse.disclose();
    } else if (retries > 0) {
      // Uses requestAnimationFrame to wait for DSFR to finish initializing => fix race condition
      requestAnimationFrame(() => this.openSection(sectionId, retries - 1));
    }
  };

  AccordionAnalytics.prototype.untrackAccordionDisplay = function (collapsible) {
    // remove hash only if it is the accordion id
    if (window.location.hash === `#${collapsible.id}`) {
      history.replaceState(null, '', '#');
    }
  };

})(this);
