// This file is adding analytics tracking for both the simulations and the regulations pages

const trackReadMoreButtons = () => {
  const showMoreBtns = document.querySelectorAll('.read-more-btn');
  showMoreBtns.forEach(btn => btn.addEventListener('click', function (evt) {
    const btn = evt.currentTarget;
    const target = btn.getAttribute('aria-controls');
    const expanded = btn.getAttribute('aria-expanded');
    const action = expanded == 'false' ? 'Expand' : 'Conceal';
    _paq.push(['trackEvent', 'Content', action, target]);
  }));
};

const trackSummaryLinks = () => {
  const summaryLinks = document.querySelectorAll('.summary-link');
  summaryLinks.forEach(link => link.addEventListener('click', function (evt) {
    const link = evt.currentTarget;
    const title = link.getAttribute('data-regulation');
    _paq.push(['trackEvent', 'Content', 'JumpToAnchor', title]);
  }));
};

const trackActionButtons = () => {
  const actionBtns = document.querySelectorAll('.action-btn');
  actionBtns.forEach(btn => btn.addEventListener('click', function (evt) {
    const btn = evt.currentTarget;
    const target = btn.getAttribute('aria-controls');
    const expanded = btn.getAttribute('aria-expanded');
    const action = expanded == 'false' ? 'ActionDetailExpand' : 'ActionDetailConceal';
    _paq.push(['trackEvent', 'Content', action, target.replace(/^action-/, "")]);
  }));
};

const trackActionLearnMoreLinks = () => {
  const actionLearnMoreLinks = document.querySelectorAll('.action-learn-more-link');
  actionLearnMoreLinks.forEach(btn => btn.addEventListener('click', function (evt) {
    const btn = evt.currentTarget;
    const actionContainer = btn.closest(".action-details-container");
    _paq.push(['trackEvent', 'Content', 'ActionDetailJumpToDetail', actionContainer.id.replace(/^action-/, "")]);
  }));
};

const trackActionTabs = () => {
  const instructorActionsTab = document.getElementById('actions-instructor-tab-1');
  if (instructorActionsTab) {
    instructorActionsTab.addEventListener('click', function () {
      _paq.push(['trackEvent', 'Content', 'ActionTabClick', 'UrbaInstructor']);
    });
  }

  const petitionerActionsTab = document.getElementById('actions-petitioner-tab-0');
  if (petitionerActionsTab) {
    petitionerActionsTab.addEventListener('click', function () {
      _paq.push(['trackEvent', 'Content', 'ActionTabClick', 'ProjectOwner']);
    });
  }
};

const trackLiabilityLink = () => {
  const liabilityLink = document.getElementById('liability-link');
  if (liabilityLink) {
    liabilityLink.addEventListener('click', function () {
      _paq.push(['trackEvent', 'SimulationContent', 'JumpToAnchor', 'LiabilityInfo']);
    });
  }
};

window.addEventListener('load', () => {
  trackReadMoreButtons();
  trackSummaryLinks();
  trackActionButtons();
  trackActionLearnMoreLinks();
  trackActionTabs();
  trackLiabilityLink();
});
