document.addEventListener("DOMContentLoaded", () => {
  const raw = document.getElementById("departments-data");
  if (!raw) return;

  const departments = JSON.parse(raw.textContent);
  const container = document.getElementById("department-combobox");
  const form = document.getElementById("simulation-form");
  const btn = document.getElementById("btn-start-simulation");
  const departmentCode = document.getElementById("department-code");
  const infoDiv = document.getElementById("department-info");
  if (!container || !btn || !form || !departmentCode) return;

  const triageUrl = btn.dataset.href;
  let selectedDept = null;

  // Le formulaire est un GET natif vers le triage. On intercepte la
  // soumission uniquement pour bloquer les départements non disponibles.
  form.addEventListener("submit", (event) => {
    if (!selectedDept || !selectedDept.is_config_valid) {
      event.preventDefault();
    }
  });

  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = "fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-btn--icon-only fr-icon-close-line department-combobox-clear";
  clearBtn.title = "Effacer";
  clearBtn.setAttribute("aria-label", "Effacer le département sélectionné");
  clearBtn.style.display = "none";

  function showDepartmentInfo(dept) {
    if (!infoDiv) return;

    if (dept.is_config_valid) {
      infoDiv.style.display = "none";
      infoDiv.innerHTML = "";
      return;
    }

    let html = "";
    if (dept.contacts_and_links) {
      html = `
        <div id="contacts_and_links" class="fr-p-2w">${dept.contacts_and_links}</div>
        <div class="fr-py-2w"><p>
          Vous représentez la DDT(M) du département et souhaitez compléter ou modifier les informations affichées ici ?
          <a href="${dept.settings_form_url}" target="_blank" rel="noopener">Cliquez ici</a>.
        </p></div>`;
    } else {
      html = `
        <div class="fr-notice fr-notice--warning">
          <div class="fr-container"><div class="fr-notice__body"><p>
            <span class="fr-notice__title"></span>
            <span class="fr-notice__desc">
              ${dept.label} : nous ne disposons pas encore d’information sur les contacts de l’administration en rapport avec la haie.
            </span>
          </p></div></div>
        </div>
        <div class="fr-py-2w"><p>
          Vous représentez la DDT(M) du département et souhaitez faire apparaître ici des informations de contact, des liens vers le site de votre préfecture,
          des ressources à présenter aux usagers ?
          <a href="${dept.settings_form_url}" target="_blank" rel="noopener">Cliquez ici</a>.
        </p></div>`;
    }

    infoDiv.innerHTML = html;
    infoDiv.style.display = "";
  }

  function hideDepartmentInfo() {
    if (!infoDiv) return;
    infoDiv.style.display = "none";
    infoDiv.innerHTML = "";
  }

  accessibleAutocomplete({
    element: container,
    id: "department",
    name: "",
    defaultValue: "",
    placeholder: "Rechercher ou choisir dans la liste",
    showAllValues: true,
    dropdownArrow: () => "",
    minLength: 0,
    source: (query, populateResults) => {
      // Normalise une chaîne pour une recherche insensible à la casse et aux
      // accents : passage en minuscules, puis décomposition Unicode NFD (qui
      // sépare chaque caractère accentué en lettre de base + signe diacritique
      // combinant), et enfin suppression de ces diacritiques combinants
      // (plage Unicode U+0300–U+036F). Ex. : "Côte-d'Or" → "cote-d'or".
      const normalize = (s) =>
        s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
      const q = normalize(query);
      populateResults(
        departments
          .filter((d) => normalize(d.label).includes(q) || d.code.includes(q))
          .map((d) => d.label)
      );
    },
    onConfirm: (value) => {
      if (!value) return;
      selectedDept = departments.find((d) => d.label === value);
      if (!selectedDept) return;

      clearBtn.style.display = "";

      if (selectedDept.is_config_valid) {
        departmentCode.value = selectedDept.code;
        btn.disabled = false;
      } else {
        departmentCode.value = "";
        btn.disabled = true;
      }

      showDepartmentInfo(selectedDept);
    },
  });

  container.appendChild(clearBtn);

  clearBtn.addEventListener("click", () => {
    document.getElementById("department").value = "";
    selectedDept = null;
    departmentCode.value = "";
    btn.disabled = true;
    clearBtn.style.display = "none";
    hideDepartmentInfo();
  });

});
