function setFieldValue (latLng) {
    const latField = document.getElementById("id_lat");
    latField.value = latLng.lat.toFixed(5);
    const lngField = document.getElementById("id_lng");
    lngField.value = latLng.lng.toFixed(5);
}

function toggleButtons () {
  const editButton = document.getElementById("map-edit-button");
  editButton.classList.add("hidden");
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
      const latLng = marker.getLatLng();
      setFieldValue(latLng);
      toggleButtons();
    });
}

window.addEventListener('mapInitialized', function (event) {

  const mapId = event.detail.id;



  if (mapId === PROJECT_MAP_ID) {
    const map = event.detail.map;
    const mapData = event.detail.data;

    initializeMarker(mapData, map);
  }
});
