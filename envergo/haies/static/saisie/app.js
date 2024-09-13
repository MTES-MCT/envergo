const { createApp, ref, onMounted, reactive } = Vue

createApp({

  // Prevent conflict with django template delimiters
  delimiters: ["[[", "]]"],


  setup() {
    const polylines = reactive([]);
    let map = null;
    let nextId = ref(0);

    const normalStyle = { className: 'hedge' };
    const hoveredStyle = {};
    const fitBoundsOptions = { padding: [25, 25] };

    const calculatePolylineLength = (latLngs) => {
      let length = 0;
      for (let i = 0; i < latLngs.length - 1; i++) {
        length += latLngs[i].distanceTo(latLngs[i + 1]);
      }
      return length;
    };

    const getAlphaIdentifier = (index) => {
      let str = '';
      while (index >= 0) {
        str = String.fromCharCode((index % 26) + 65) + str;
        index = Math.floor(index / 26) - 1;
      }
      return str;
    };

    const updatePolylineIds = () => {
      polylines.forEach((polyline, index) => {
        polyline.id = getAlphaIdentifier(index);
      });
    };

    const startDrawing = () => {
      let currentPolyline = map.editTools.startPolyline(null, normalStyle);
      const polylineId = getAlphaIdentifier(nextId.value++);
      const polylineData = reactive({
        id: polylineId,
        polylineLayer: currentPolyline,
        latLngs: currentPolyline.getLatLngs(),
        length: 0,
        isHovered: false
      });
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

      // Centrer la carte sur la polyline lors du clic
      currentPolyline.on('click', () => {
        const bounds = currentPolyline.getBounds();
        map.fitBounds(bounds, fitBoundsOptions);
      });

      // Gérer l'état de survol pour la polyline
      currentPolyline.on('mouseover', () => {
        currentPolyline.setStyle(hoveredStyle);
        currentPolyline._path.classList.add("hovered");
        polylineData.isHovered = true;
      });

      currentPolyline.on('mouseout', () => {
        currentPolyline.setStyle(normalStyle);
        currentPolyline._path.classList.remove("hovered");
        polylineData.isHovered = false;

      });
    };

    const removePolyline = (index, event) => {
      polylines[index].polylineLayer.remove();
      polylines.splice(index, 1);
      updatePolylineIds(); // Mettre à jour les identifiants après suppression
      nextId.value = polylines.length; // Réinitialiser le prochain identifiant

      // Stop the event to bubble, triggering the list "click" event that would
      // center the map on the deleted polyline
      event.stopPropagation();
    };

    const handleMouseOver = (polyline) => {
      polyline.polylineLayer.setStyle(hoveredStyle);
      if (Object.hasOwn(polyline.polylineLayer, "_path")) {
        polyline.polylineLayer._path.classList.add("hovered");
      }

    };

    const handleMouseOut = (polyline) => {
      polyline.polylineLayer.setStyle(normalStyle);
      if (Object.hasOwn(polyline.polylineLayer, "_path")) {
        polyline.polylineLayer._path.classList.remove("hovered");
      }
    };

    // Centrer la carte sur la polyline lorsque l'utilisateur clique sur l'entrée dans la liste
    const handleClickOnList = (polyline) => {
      const bounds = polyline.polylineLayer.getBounds();
      map.fitBounds(bounds, fitBoundsOptions);
    };

    const zoomOut = () => {
      if (polylines.length > 0) {
        const group = new L.featureGroup(polylines.map(p => p.polylineLayer));
        map.fitBounds(group.getBounds(), fitBoundsOptions);
      }
    };

    // Initialiser la carte Leaflet après le montage du composant
    onMounted(() => {
      map = L.map('map', {
        editable: true,
        doubleClickZoom: false,
      }).setView([43.6861, 3.5911], 17);

      // Ajouter une couche de tuiles
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
      }).addTo(map);
    });

    return {
      polylines,
      startDrawing,
      removePolyline,
      handleMouseOver,
      handleMouseOut,
      handleClickOnList,
      zoomOut,
    };
  }
}).mount('#app');
