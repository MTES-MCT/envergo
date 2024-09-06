const { createApp, ref, onMounted } = Vue

createApp({

  // Prevent conflict with django template delimiters
  delimiters: ["[[", "]]"],


  setup() {
    const polylines = ref([]);

    const calculatePolylineLength = (latLngs) => {
      let length = 0;
      for (let i = 0; i < latLngs.length - 1; i++) {
        length += latLngs[i].distanceTo(latLngs[i + 1]);
      }
      return length;
    };

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
          polylines.value.push({ latLngs: currentPolyline.getLatLngs(), length: 0 });
        }
        currentPolyline.addLatLng(e.latlng);

        const index = polylines.value.length - 1;
        polylines.value[index].latLngs = currentPolyline.getLatLngs();
        polylines.value[index].length = calculatePolylineLength(currentPolyline.getLatLngs());
      });

      // Terminer la polyline au double-clic
      map.on('dblclick', (evt) => {
        if (currentPolyline) {
          currentPolyline = null;
        }
      });
    });

    return {
      polylines,
    };
  },
}).mount('#app');
