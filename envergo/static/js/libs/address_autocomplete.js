/**
 * Enrich the address field with an autocomplete feature.
 */
(function(exports, accessibleAutocomplete) {
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
  const AddressAutocomplete = function(fieldName) {
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
  AddressAutocomplete.prototype.updateCurrentInput = function() {
    this.inputElement.id = `${this.inputId}-input`;
    this.inputElement.style.display = 'none';
    this.inputElement.name = '';
  };

  /**
   * Calls the autocomplete library to create a new input field.
   **/
  AddressAutocomplete.prototype.enableAutocomplete = function() {

    this.inputElement.parentNode.insertBefore(this.autocompleteContainer, this.inputElement);

    accessibleAutocomplete({
      element: this.autocompleteContainer,
      id: this.inputId,
      minLength: 3,
      name: this.inputName,
      defaultValue: this.inputElement.value,
      templates: {
        inputValue: function(item) {
          if (typeof item === 'string') return item;

          const value = item ? item.properties.label : '';
          return value;
        },
        suggestion: function(item) {
          if (typeof item === 'string') return item;

          return `<div>
              <strong>${item.properties.label}</strong> <br />
              <span>
                ${item.properties.context}
              </span>
            </div>`;
        }
      },
      tNoResults: () => 'Aucun r??sultat trouv??',
      tStatusQueryTooShort: (minQueryLength) => `Saisissez au moins ${minQueryLength} caract??res pour voir des r??sultats`,
      tStatusNoResults: () => 'Aucun r??sultat de recherche',
      tStatusSelectedOption: (selectedOption, length, index) => `${selectedOption} ${index + 1} de ${length} est en surbrillance`,
      tStatusResults: function(length, contentSelectedOption) {
        let result;
        if (length === 1) {
          result = `<span>1 r??sultat disponible. ${contentSelectedOption}</span>`;
        } else {
          result = `<span>${length} r??sultats disponibles. ${contentSelectedOption}</span>`;
        }
        return result;
      },
      tAssistiveHint: function() {
        return "Quand des r??sultats d'autocompl??tion sont disponibles, utilisez " +
          "les fl??ches haut et bas pour les parcourir. Utilisez entr??e pour " +
          "s??lectionner. Sur p??riph??rique tactile, explorez en glissant le doigt.";
      },
      onConfirm: function(val) {
        if (val === undefined || !val.hasOwnProperty('properties')) return;

        if (val) {
          const eventData = {
            communeName: val.properties.city,
            citycode: val.properties.citycode,
            coordinates: val.geometry.coordinates,
          };
          const event = new CustomEvent('EnvErgo:citycode_selected', { detail: eventData });
          window.dispatchEvent(event);
        }
      },
      source: function(query, populateResults) {
        return debouncedFetch(`https://api-adresse.data.gouv.fr/search/?type=housenumber&autocomplete=1&q=${query}`)
          .then((response) => response.json())
          .then(({ features }) => {
            populateResults(features);
          })
          .catch((error) => console.log(error));
      }
    });
  };

})(this, accessibleAutocomplete);


window.addEventListener('load', function() {
  new AddressAutocomplete(ADDRESS_AUTOCOMPLETE_FIELD_NAME || 'address');
});
