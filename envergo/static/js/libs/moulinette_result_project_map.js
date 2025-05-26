function setFieldValue (latLng) {
    const latField = document.getElementById("id_lat");
    latField.value = latLng.lat.toFixed(5);
    const lngField = document.getElementById("id_lng");
    lngField.value = latLng.lng.toFixed(5);
}

function displayButton () {
  const refreshButton = document.getElementById("map-refresh-button");
  refreshButton.classList.add("display");
}

function initializeMarker(mapData, map) {
  const center = mapData.center;
  const centerCoords = [center.coordinates[1], center.coordinates[0]];

  const options = {
    draggable: true,
    autoPan: false,
  };

  const marker = L.marker(centerCoords, options);
  marker.addTo(map);

  marker.on('moveend', function (event) {
      _paq.push(['trackEvent', 'Content', 'MapMoveCursor']);
      const latLng = marker.getLatLng();
      setFieldValue(latLng);
      displayButton();
    });

  return marker;
}

window.addEventListener('mapInitialized', function (event) {
  const mapId = event.detail.id;

  if (mapId === PROJECT_MAP_ID) {
    const map = event.detail.map;
    const mapData = event.detail.data;

    const marker = initializeMarker(mapData, map);

    map.on('dblclick', function(e) {
      _paq.push(['trackEvent', 'Content', 'MapDblClick']);
      marker.setLatLng(e.latlng);
      setFieldValue(e.latlng);
      displayButton();
    });

    const moulinetteForm = document.getElementById("moulinette-form");
    moulinetteForm.addEventListener('submit', function (event) {
      _paq.push(['trackEvent', 'Content', 'Update', 'Map']);

      // disable the marker dragging, and the edition buttons when the form is submitted
      marker.dragging.disable();

      const editButtons = document.querySelectorAll('.moulinette-edit-button');
      editButtons.forEach(button => {
        if(button.tagName.toLowerCase() === 'a')
        {
          button.removeAttribute('href');
        }
        else{
          button.disabled = true;
        }
      });
    });

  }
});
