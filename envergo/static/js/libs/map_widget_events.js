// Log and event when a choice is selected in the address autocomplete widget
window.addEventListener('Envergo:citycode_selected', function () {
  _paq.push(['trackEvent', 'Form', 'AddressChoose']);
}, { once: true });

// Log an event when the address autocomplete widget is used
window.addEventListener('Envergo:address_autocomplete_populated', function (evt) {
  _paq.push(['trackEvent', 'Form', 'AddressType']);
}, { once: true });

// Log an event when the map widget marker is moved
window.addEventListener('Envergo:map_marker_moved', function (evt) {
  _paq.push(['trackEvent', 'Form', 'MapMoveCursor']);
}, { once: true });

// Log an event when the map is double-clicked
window.addEventListener('Envergo:map_dbl_clicked', function (evt) {
  _paq.push(['trackEvent', 'Form', 'MapDblClick']);
}, { once: true });
