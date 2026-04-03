window.addEventListener("load", function () {
  var raw = document.getElementById("departments-data");
  if (!raw) return;
  var departments = JSON.parse(raw.textContent);

  var byLabel = {};
  departments.forEach(function (d) {
    byLabel[d.label] = d;
  });

  var container = document.getElementById("department-combobox");
  var infoContainer = document.getElementById("contacts-info-container");
  if (!container || !infoContainer) return;

  var urlCode = new URLSearchParams(window.location.search).get("department");
  var preSelected = urlCode
    ? departments.find(function (d) {
        return d.code === urlCode;
      })
    : null;

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
        var q = query.toLowerCase();
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
      if (!value) return;
      var dept = byLabel[value];
      if (!dept) return;
      showContactInfo(dept);
      var url = new URL(window.location);
      url.searchParams.set("department", dept.code);
      history.replaceState({}, "", url);
      clearBtn.style.display = "";
    },
  });

  if (preSelected) showContactInfo(preSelected);

  var clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = "fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-btn--icon-only fr-icon-close-line department-combobox-clear";
  clearBtn.title = "Effacer";
  clearBtn.setAttribute("aria-label", "Effacer le département sélectionné");
  clearBtn.style.display = preSelected ? "" : "none";
  container.appendChild(clearBtn);

  clearBtn.addEventListener("click", function () {
    document.getElementById("department").value = "";
    infoContainer.innerHTML = "";
    var url = new URL(window.location);
    url.searchParams.delete("department");
    history.replaceState({}, "", url);
    clearBtn.style.display = "none";
  });

  function showContactInfo(dept) {
    if (dept.contacts_info) {
      infoContainer.innerHTML =
        '<div class="fr-highlight fr-mt-4w fr-p-2w">' +
        dept.contacts_info +
        "</div>";
    } else {
      infoContainer.innerHTML =
        '<p class="fr-text--sm fr-my-2w fr-error-text">' +
        "Les coordonnées du guichet unique dans ce département ne sont pas encore disponibles." +
        "</p>";
    }
  }
});
