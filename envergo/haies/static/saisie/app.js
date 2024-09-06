const { createApp, ref, onMounted, reactive } = Vue

createApp({

  // Prevent conflict with django template delimiters
  delimiters: ["[[", "]]"],


  setup() {
    const polylines = reactive([]);
    let map = null;

    const calculatePolylineLength = (latLngs) => {
      let length = 0;
      for (let i = 0; i < latLngs.length - 1; i++) {
        length += latLngs[i].distanceTo(latLngs[i + 1]);
      }
      return length;
    };

    const startDrawing = () => {
      let currentPolyline = map.editTools.startPolyline();
      // let index = polylines.length;

      const polylineData = reactive({ latLngs: currentPolyline.getLatLngs(), length: 0 });
      polylines.push(polylineData);

      // Mettre à jour les informations en temps réel pendant le dessin
      currentPolyline.on('editable:vertex:new', () => {
        polylineData.latLngs = [...currentPolyline.getLatLngs()];
        polylineData.length = calculatePolylineLength(currentPolyline.getLatLngs());
      });

      // Mettre à jour les informations en temps réel pendant le déplacement
      currentPolyline.on('editable:vertex:dragend', () => {
        polylineData.latLngs = [...currentPolyline.getLatLngs()];
        polylineData.length = calculatePolylineLength(currentPolyline.getLatLngs());
      });
    };

    // Initialiser la carte Leaflet après le montage du composant
    onMounted(() => {
      map = L.map('map', {
        editable: true,
        doubleClickZoom: false,
        draggable: true,
      }).setView([43.6861, 3.5911], 17);

      // Ajouter une couche de tuiles
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
      }).addTo(map);
    });

    return {
      polylines,
      startDrawing,
    };
  }
}).mount('#app');
