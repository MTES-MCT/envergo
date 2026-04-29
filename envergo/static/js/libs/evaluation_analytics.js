const trackEvaluationVisit = () => {
  _paq.push(['trackEvent', 'Evaluation', 'Visit', DEPARTMENT]);
};

const trackAppointmentButton = () => {
  const pickAppointmentBtn = document.getElementById("pick-appointment-btn");
  if (!pickAppointmentBtn) {
    return;
  }
  pickAppointmentBtn.addEventListener("click", function () {
    _paq.push(["trackEvent", "Evaluation", "ChooseAppointmentClick"]);
  });
};

const trackSelfDeclarationButtons = () => {
  const ctaButtons = document.querySelectorAll('.self-declaration-cta');
  ctaButtons.forEach(btn => btn.addEventListener('click', function (evt) {
    evt.preventDefault();
    const btn = evt.currentTarget;

    let url = EVENTS_URL;
    let token = CSRF_TOKEN;
    let headers = { "X-CSRFToken": token };
    let data = new FormData();
    data.append("category", "compliance");
    data.append("action", "page-click");
    data.append("metadata", btn.getAttribute("data-sql-event-metadata"));
    fetch(url, { headers: headers, body: data, method: 'POST' })
      .finally(function () { window.location = btn.href; });
  }));
};

// Cette méthode utilise le local storage sans demander de permission explicite à l'utilisateur.
// Cette permission n'est pas nécessaire au regard du RGPD car il s'agit d'une personnalisation de l'UI expressement demandées par l'utilisateur.
// cf https://www.cnil.fr/fr/cookies-et-autres-traceurs/regles/cookies/comment-mettre-mon-site-web-en-conformite
// > "Les traceurs qui sont exemptés de consentement [sont les traceurs] strictement nécessaires à la fourniture
// d'un service de communication en ligne expressément demandé par l'utilisateur…"
// > "les traceurs de personnalisation de l'interface utilisateur…"
const trackSelfDeclarationDismiss = () => {
  const key = "self-declaration-cta-dismissed";
  const el = document.getElementById("self-declaration-cta-v2");
  if (!el) {
    return;
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
};

const trackEvaluationLiabilityLink = () => {
  const liabilityLink = document.getElementById('evaluation-liability-link');
  if (liabilityLink) {
    liabilityLink.addEventListener('click', function () {
      _paq.push(['trackEvent', 'EvaluationContent', 'JumpToAnchor', 'LiabilityInfo']);
    });
  }
};

window.addEventListener('load', () => {
  trackEvaluationVisit();
  trackAppointmentButton();
  trackSelfDeclarationButtons();
  trackSelfDeclarationDismiss();
  trackEvaluationLiabilityLink();
});
