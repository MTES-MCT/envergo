document.addEventListener("DOMContentLoaded", function () {
  const raw = document.getElementById("departments-data");
  if (!raw) {
    return;
  }
  const departments = JSON.parse(raw.textContent);

  const container = document.getElementById("department-combobox");
  const infoContainer = document.getElementById("contacts-info-container");
  if (!container || !infoContainer) return;

  const urlCode = new URLSearchParams(window.location.search).get("department");
  const preSelected = urlCode
    ? departments.find(function (d) {
        return d.code === urlCode;
      })
    : null;

  const clearBtn = document.createElement("button");
  function showContactInfo(dept) {
    if (dept.contacts_info) {
      let html = `<div class="fr-highlight fr-mt-4w">${dept.contacts_info}</div>`;
      if (!dept.is_config_valid) {
        html += `<p class="fr-mt-2w">À noter&nbsp;: le portail du guichet unique de la haie n'est pas encore activé dans le département ${dept.label}.</p>`;
      }
      infoContainer.innerHTML = html;
    } else {
      infoContainer.innerHTML = `<p class="fr-text--sm fr-my-2w fr-error-text">Les coordonnées du guichet unique dans ce département ne sont pas encore disponibles.</p>`;
    }
  }

  accessibleAutocomplete({
    element: container,
    id: "department",
    name: "department_label",
    defaultValue: preSelected ? preSelected.label : "",
    placeholder: "Rechercher ou choisir dans la liste",
    showAllValues: true,
    dropdownArrow: () => '',
    minLength: 0,
    source: function (query, populateResults) {
      if (query.length < 2) {
        populateResults(
          departments.map(function (d) {
            return d.label;
          })
        );
      } else {
        const q = query.toLowerCase();
        populateResults(
          departments
            .filter(function (d) {
              return (
                d.label.toLowerCase().indexOf(q) !== -1 ||
                d.code.toLowerCase().indexOf(q) !== -1
              );
            })
            .map(function (d) {
              return d.label;
            })
        );
      }
    },
    onConfirm: function (value) {
      if (!value) {
        return;
      }
      const dept = departments.find((d) => d.label === value);
      if (!dept) {
        console.warn("department_combobox: département introuvable pour", value);
        return;
      }
      showContactInfo(dept);
      const url = new URL(window.location);
      url.searchParams.set("department", dept.code);
      history.replaceState({}, "", url);
      clearBtn.style.display = "";
    },
  });

  if (preSelected) showContactInfo(preSelected);


  clearBtn.type = "button";
  clearBtn.className = "fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-btn--icon-only fr-icon-close-line department-combobox-clear";
  clearBtn.title = "Effacer";
  clearBtn.setAttribute("aria-label", "Effacer le département sélectionné");
  clearBtn.style.display = preSelected ? "" : "none";
  container.appendChild(clearBtn);

  clearBtn.addEventListener("click", function () {
    document.getElementById("department").value = "";
    infoContainer.innerHTML = "";
    const url = new URL(window.location);
    url.searchParams.delete("department");
    history.replaceState({}, "", url);
    clearBtn.style.display = "none";
  });
});
