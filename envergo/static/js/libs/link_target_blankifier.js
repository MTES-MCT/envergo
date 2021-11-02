/**
 * Helper to add the `target=_blank` attribute for main content links.
 */
(function(exports) {
  const LinkTargetBlankifier = function() {};
  exports.LinkTargetBlankifier = LinkTargetBlankifier;

  /**
   * Set's the target=blank attribute on all `a` children of the given node.
   */
  LinkTargetBlankifier.prototype.blankify = function(node) {
    const links = node.querySelectorAll('a');
    links.forEach(link => {
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener');
    });
  };
})(this);
