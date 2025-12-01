// This file is adding analytics tracking for both the simulations and the regulations pages

// Track an event when a regulation main "read more" btn is clicked
window.addEventListener('load', function () {
  const showMoreBtns = document.querySelectorAll('.read-more-btn');
  showMoreBtns.forEach(btn => btn.addEventListener('click', function (evt) {
    const btn = evt.currentTarget;
    const target = btn.getAttribute('aria-controls');
    const expanded = btn.getAttribute('aria-expanded');
    const action = expanded == 'false' ? 'Expand' : 'Conceal';
    _paq.push(['trackEvent', 'Content', action, target]);
  }));
});

// Track when a summary link is clicked
window.addEventListener('load', function () {
  const summaryLinks = document.querySelectorAll('.summary-link');
  summaryLinks.forEach(link => link.addEventListener('click', function (evt) {
    // Log the event
    const link = evt.currentTarget;
    const title = link.getAttribute('data-regulation');
    _paq.push(['trackEvent', 'Content', 'JumpToAnchor', title]);
  }));
});

// Track when an action to take accordion is toggled
window.addEventListener('load', function () {
  const actionBtns = document.querySelectorAll('.action-btn');
  actionBtns.forEach(btn => btn.addEventListener('click', function (evt) {
    const btn = evt.currentTarget;
    const target = btn.getAttribute('aria-controls');
    const expanded = btn.getAttribute('aria-expanded');
    const action = expanded == 'false' ? 'ActionDetailExpand' : 'ActionDetailConceal';
    _paq.push(['trackEvent', 'Content', action, target.replace(/^action-/, "")]);
  }));
});

// Track when an action to take learn more link is clicked
window.addEventListener('load', function () {
  const  actionLearnMoreLinks = document.querySelectorAll('.action-learn-more-link');
  actionLearnMoreLinks.forEach(btn => btn.addEventListener('click', function (evt) {
    const btn = evt.currentTarget;
    const actionContainer = btn.closest(".action-details-container");
    actionContainer.id;
    _paq.push(['trackEvent', 'Content', 'ActionDetailJumpToDetail', actionContainer.id.replace(/^action-/, "")]);
  }));
});


// Track when an actions to take tab is browsed
window.addEventListener('load', function () {
  const  instructorActionsTab = document.getElementById('actions-instructor-tab-1');
  if(instructorActionsTab) {
    instructorActionsTab.addEventListener('click', function (evt) {
      _paq.push(['trackEvent', 'Content', 'ActionTabClick', 'UrbaInstructor']);
    });
  }

  const  petitionerActionsTab = document.getElementById('actions-petitioner-tab-0');
  if(petitionerActionsTab) {
    petitionerActionsTab.addEventListener('click', function (evt) {
      _paq.push(['trackEvent', 'Content', 'ActionTabClick', 'ProjectOwner']);
    });
  }
});
