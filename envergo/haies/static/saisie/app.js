const { createApp, ref, onMounted, reactive } = Vue

const normalStyle = { className: 'hedge' };
const hoveredStyle = {};
const fitBoundsOptions = { padding: [25, 25] };

class Polyline {
  constructor(map, id, onRemove) {
    this.id = id;
    this.map = map;
    this.onRemove = onRemove;
    this.polylineLayer = map.editTools.startPolyline(null, normalStyle);
    this.latLngs = this.polylineLayer.getLatLngs();
    this.length = this.calculateLength();
    this.isHovered = false;

    this.polylineLayer.on('editable:vertex:new', this.updateLength.bind(this));
    this.polylineLayer.on('editable:vertex:dragend', this.updateLength.bind(this));
    this.polylineLayer.on('click', this.centerOnMap.bind(this));
    this.polylineLayer.on('mouseover', this.handleMouseOver.bind(this));
    this.polylineLayer.on('mouseout', this.handleMouseOut.bind(this));
  }

  calculateLength() {
    let length = 0;
    for (let i = 0; i < this.latLngs.length - 1; i++) {
      length += this.latLngs[i].distanceTo(this.latLngs[i + 1]);
    }
    return length;
  }

  updateLength() {
    this.latLngs = this.polylineLayer.getLatLngs();
    this.length = this.calculateLength();
  }

  handleMouseOver() {
    this.polylineLayer.setStyle(hoveredStyle);
    this.isHovered = true;
    if (this.polylineLayer._path) {
      this.polylineLayer._path.classList.add("hovered");
    }
  }

  handleMouseOut() {
    this.polylineLayer.setStyle(normalStyle);
    this.isHovered = false;
    if (this.polylineLayer._path) {
      this.polylineLayer._path.classList.remove("hovered");
    }
  }

  centerOnMap() {
    const bounds = this.polylineLayer.getBounds();
    this.map.fitBounds(bounds, { padding: [25, 25] });
  }

  remove() {
    this.polylineLayer.remove();
    this.onRemove(this);
  }
}

createApp({

  // Prevent conflict with django template delimiters
  delimiters: ["[[", "]]"],

  setup() {
    const polylines = reactive([]);
    let map = null;
    let nextId = ref(0);

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
      const polylineId = getAlphaIdentifier(nextId.value++);
      const polyline = reactive(new Polyline(map, polylineId, removePolyline));
      polylines.push(polyline);
    };

    const removePolyline = (polyline) => {
      let index = polylines.indexOf(polyline);
      polylines.splice(index, 1);
      updatePolylineIds();
      nextId.value = polylines.length;
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
      zoomOut,
    };
  }
}).mount('#app');
