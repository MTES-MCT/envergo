document.addEventListener("DOMContentLoaded", () => {
  const raw = document.getElementById("departments-data");
  if (!raw) return;

  const departments = JSON.parse(raw.textContent);
  const container = document.getElementById("department-combobox");
  const btn = document.getElementById("btn-start-simulation");
  const infoDiv = document.getElementById("department-info");
  if (!container || !btn) return;

  const triageUrl = btn.dataset.href;
  let selectedDept = null;

  btn.addEventListener("click", () => {
    if (!btn.disabled && btn.dataset.href) {
      window.location.href = btn.dataset.href;
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
      html +=
        '<div id="contacts_and_links" class="fr-p-2w">' +
        dept.contacts_and_links +
        "</div>" +
        '<div class="fr-py-2w"><p>' +
        "Vous représentez la DDT(M) du département et souhaitez compléter ou modifier les informations affichées ici ? " +
        '<a href="https://tally.so/r/w4Agpb" target="_blank" rel="noopener">Cliquez ici</a>.' +
        "</p></div>";
    } else {
      html +=
        '<div class="fr-notice fr-notice--warning">' +
        '<div class="fr-container"><div class="fr-notice__body"><p>' +
        '<span class="fr-notice__title"></span>' +
        '<span class="fr-notice__desc">' +
        dept.label +
        " : nous ne disposons pas encore d’information sur les contacts de l’administration en rapport avec la haie." +
        "</span></p></div></div></div>" +
        '<div class="fr-py-2w"><p>' +
        "Vous représentez la DDT(M) du département et souhaitez faire apparaître ici des informations de contact, des liens vers le site de votre préfecture, " +
        "des ressources à présenter aux usagers ? " +
        '<a href="https://tally.so/r/w4Agpb" target="_blank" rel="noopener">Cliquez ici</a>.' +
        "</p></div>";
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
    name: "department_label",
    defaultValue: "",
    placeholder: "Rechercher ou choisir dans la liste",
    showAllValues: true,
    dropdownArrow: () => "",
    minLength: 0,
    source: (query, populateResults) => {
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
        btn.dataset.href = triageUrl + "?department=" + encodeURIComponent(selectedDept.code);
        btn.disabled = false;
      } else {
        btn.dataset.href = triageUrl;
        btn.disabled = true;
      }

      showDepartmentInfo(selectedDept);
    },
  });

  container.appendChild(clearBtn);

  clearBtn.addEventListener("click", () => {
    document.getElementById("department").value = "";
    selectedDept = null;
    btn.dataset.href = triageUrl;
    btn.disabled = true;
    clearBtn.style.display = "none";
    hideDepartmentInfo();
  });

});
