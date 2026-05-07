document.addEventListener("DOMContentLoaded", () => {
  const raw = document.getElementById("departments-data");
  if (!raw) return;

  const departments = JSON.parse(raw.textContent);
  const container = document.getElementById("department-combobox");
  const btn = document.getElementById("btn-start-simulation");
  if (!container || !btn) return;

  const triageUrl = btn.getAttribute("href");
  let selectedDept = null;

  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = "fr-btn fr-btn--tertiary-no-outline fr-btn--sm fr-btn--icon-only fr-icon-close-line department-combobox-clear";
  clearBtn.title = "Effacer";
  clearBtn.setAttribute("aria-label", "Effacer le département sélectionné");
  clearBtn.style.display = "none";

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
      btn.href = triageUrl + "?department=" + selectedDept.code;
      delete btn.dataset.disabled;
      btn.setAttribute("aria-disabled", "false");
      clearBtn.style.display = "";
    },
  });

  container.appendChild(clearBtn);

  clearBtn.addEventListener("click", () => {
    document.getElementById("department").value = "";
    selectedDept = null;
    btn.href = triageUrl;
    btn.dataset.disabled = "true";
    btn.setAttribute("aria-disabled", "true");
    clearBtn.style.display = "none";
  });

});
