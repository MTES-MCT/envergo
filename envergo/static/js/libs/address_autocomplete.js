/**
 * Enrich the address field with an autocomplete feature.
 */
(function (exports, accessibleAutocomplete) {
  'use strict';

  function debouncePromise(fn, time) {
    let timerId = undefined;

    return function debounced(...args) {
      if (timerId) {
        clearTimeout(timerId);
      }

      return new Promise((resolve) => {
        timerId = setTimeout(() => resolve(fn(...args)), time);
      });
    };
  }

  /**
   * Create a debounced version of fetch.
   *
   * This prevents spamming the api endoint with too many requests.
   **/
  const debouncedFetch = debouncePromise(fetch, 150);


  /**
   * Initialize the autocomplete element.
   **/
  const AddressAutocomplete = function (fieldName) {
    this.inputName = fieldName;
    this.inputId = `id_${fieldName}`;
    this.inputElement = document.getElementById(this.inputId);
    this.autocompleteContainer = document.createElement('div');

    this.updateCurrentInput();
    this.enableAutocomplete();
  };
  exports.AddressAutocomplete = AddressAutocomplete;

  /**
   * Hides the existing input to make room for the new one.
   **/
  AddressAutocomplete.prototype.updateCurrentInput = function () {
    this.inputElement.id = `${this.inputId}-input`;
    this.inputElement.style.display = 'none';
    this.inputElement.name = '';
  };

  /**
   * Calls the autocomplete library to create a new input field.
   **/
  AddressAutocomplete.prototype.enableAutocomplete = function () {

    this.inputElement.parentNode.insertBefore(this.autocompleteContainer, this.inputElement);

    let inputId = this.inputId;

    accessibleAutocomplete({
      element: this.autocompleteContainer,
      id: this.inputId,
      minLength: 3,
      name: this.inputName,
      defaultValue: this.inputElement.value,
      placeholder: this.inputElement.placeholder,
      templates: {
        inputValue: function (item) {
          if (typeof item === 'string') return item;

          const value = item ? item.properties.label : '';
          return value;
        },
        suggestion: function (item) {
          if (typeof item === 'string') return item;

          return `<div>
              <strong>${item.properties.label}</strong> <br />
              <span>
                ${item.properties.context}
              </span>
            </div>`;
        }
      },
      tNoResults: () => 'Aucun résultat trouvé',
      tStatusQueryTooShort: (minQueryLength) => `Saisissez au moins ${minQueryLength} caractères pour voir des résultats`,
      tStatusNoResults: () => 'Aucun résultat de recherche',
      tStatusSelectedOption: (selectedOption, length, index) => `${selectedOption} ${index + 1} de ${length} est en surbrillance`,
      tStatusResults: function (length, contentSelectedOption) {
        let result;
        if (length === 1) {
          result = `<span>1 résultat disponible. ${contentSelectedOption}</span>`;
        } else {
          result = `<span>${length} résultats disponibles. ${contentSelectedOption}</span>`;
        }
        return result;
      },
      tAssistiveHint: function () {
        return "Quand des résultats d'autocomplétion sont disponibles, utilisez " +
          "les flèches haut et bas pour les parcourir. Utilisez entrée pour " +
          "sélectionner. Sur périphérique tactile, explorez en glissant le doigt.";
      },
      onConfirm: function (val) {
        if (val === undefined || !val.hasOwnProperty('properties')) return;

        if (val) {
          const eventData = {
            communeName: val.properties.city,
            citycode: val.properties.citycode,
            coordinates: val.geometry.coordinates,
            department: val.properties.context?.split(",")[0],
          };
          const event = new CustomEvent('Envergo:citycode_selected', { detail: eventData });
          window.dispatchEvent(event);

          // Force blurring current input, so the keyboard is closed on mobile
          // Also, we have to add a small delay because otherwise, other events have not
          // stopped firing so the field keeps it's focus
          setTimeout(() => { document.getElementById(inputId).blur(); }, 250);
        }
      },
      source: function (query, populateResults) {
        const event = new CustomEvent('Envergo:address_autocomplete_input', { detail: query });
        window.dispatchEvent(event);
        return debouncedFetch(`https://data.geopf.fr/geocodage/search/?autocomplete=1&q=${query}`)
          .then((response) => response.json())
          .then(({ features }) => {
            populateResults(features);
            const event = new CustomEvent('Envergo:address_autocomplete_populated', { detail: features });
            window.dispatchEvent(event);
          })
          .catch((error) => console.log(error));
      }
    });

    const observer = new MutationObserver(() => {
      const autocompleteInput = this.autocompleteContainer.querySelector('input');
      if (this.inputElement.disabled) {
        if (autocompleteInput) {
          autocompleteInput.setAttribute('disabled', 'true');
        }
      } else {
        if (autocompleteInput) {
          autocompleteInput.removeAttribute('disabled');
        }
      }
    });

    observer.observe(this.inputElement, { attributes: true, attributeFilter: ['disabled'] });
  };

})(this, accessibleAutocomplete);


window.addEventListener('load', function () {
  new AddressAutocomplete(ADDRESS_AUTOCOMPLETE_FIELD_NAME || 'address');
});
