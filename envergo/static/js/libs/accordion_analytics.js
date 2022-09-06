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
(function(exports) {
  'use strict';

  const AccordionAnalytics = function(accordionElt) {
    this.accordionElt = accordionElt;
    this.currentHash = window.location.hash.substring(1);
    this.init();

    if (this.currentHash) {
      this.openSection(this.currentHash);
    }
  };
  exports.AccordionAnalytics = AccordionAnalytics;

  AccordionAnalytics.prototype.init = function() {
    const collapsibles = this.accordionElt.querySelectorAll('.fr-collapse');
    collapsibles.forEach(this.observeCollapsible.bind(this));
  };

  /**
   * Setup the mutation observers to detect sections opening.
   */
  AccordionAnalytics.prototype.observeCollapsible = function(collapsible) {

    // This will be fired whenever the element's dom is mutated
    const callback = function(mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
          const expanded = collapsible.classList.contains('fr-collapse--expanded');

          if (expanded) {
            this.trackAccordionDisplay(collapsible.id);
          } else {
            this.untrackAccordionDisplay();
          }
        }
      }.bind(this));
    };

    const observer = new MutationObserver(callback.bind(this));
    observer.observe(collapsible, { attributes: true });
  };

  AccordionAnalytics.prototype.trackAccordionDisplay = function(id) {
    history.replaceState(null, '', `#${id}`);
    // replaceState does not fire a `hashchange` event so we have to
    // to that manually
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  };

  /**
   * Trigger one accordion section's opening
   */
  AccordionAnalytics.prototype.openSection = function(sectionId) {
    const button = this.accordionElt.querySelector(`[aria-controls=${sectionId}]`);
    if (button) {
      // Directly clicking on the button randomly does not work
      // Using a slight timeout seems to do the trick.
      window.setTimeout(function() { button.click(); }, 50);
    }
  };

  AccordionAnalytics.prototype.untrackAccordionDisplay = function() {
    history.replaceState(null, '', '#');
  };

})(this);
