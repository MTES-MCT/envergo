const { createApp, ref, onMounted } = Vue

createApp({
  delimiters: ["[[", "]]"],
  setup() {
    const polylines = ref([]);

    // Initialiser la carte Leaflet après le montage du composant
    onMounted(() => {
      const map = L.map('map').setView([43.6861, 3.5911], 17);
      map.doubleClickZoom.disable();

      // Ajouter une couche de tuiles
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
      }).addTo(map);

      let currentPolyline = null;

      // Ajouter la fonctionnalité de dessin de polylines
      map.on('click', (e) => {
        if (!currentPolyline) {
          currentPolyline = L.polyline([], { color: 'red' }).addTo(map);
        }
        currentPolyline.addLatLng(e.latlng);
      });

      // Terminer la polyline au double-clic
      map.on('dblclick', (evt) => {
        if (currentPolyline) {
          polylines.value.push(currentPolyline.getLatLngs());
          currentPolyline = null;
        }

        debugger;
        evt.preventDefault();
      });
    });

    return {
      polylines,
    };
  },
}).mount('#app');
