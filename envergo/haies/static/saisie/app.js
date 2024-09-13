const { createApp, ref, onMounted, reactive } = Vue

const normalStyle = { className: 'hedge' };
const hoveredStyle = {};
const fitBoundsOptions = { padding: [25, 25] };


/**
 * Represent a single hedge object.
 *
 * @param {L.Map} map - The Leaflet map object.
 * @param {string} id - The identifier of the hedge (A, B, …, AA, AB, …).
 * @param {function} onRemove - The callback function to call when the hedge is removed.
 */
class Hedge {
  constructor(map, id, onRemove) {
    this.id = id;
    this.map = map;
    this.onRemove = onRemove;
    this.polyline = map.editTools.startPolyline(null, normalStyle);
    this.isHovered = false;
    this.latLngs = [];
    this.length = 0;
  }

  /**
   * Set up event listeners and initialize object.
   *
   * INFO this code CANNOT be moved inside the constructor, because it prevent vue reactivity
   * to work.
   *
   * Indeed, such an object is meant to be initialized like this:
   * let hedge = reactive(new Hedge(map, id, onRemove));
   * hedge.init();
   *
   * That way hedge is a proxy object, and methods with side effects (like `updateLength`)
   * will trigger reactivity.
   */
  init() {
    this.updateLength();

    this.polyline.on('editable:vertex:new', this.updateLength.bind(this));
    this.polyline.on('editable:vertex:dragend', this.updateLength.bind(this));
    this.polyline.on('click', this.centerOnMap.bind(this));
    this.polyline.on('mouseover', this.handleMouseOver.bind(this));
    this.polyline.on('mouseout', this.handleMouseOut.bind(this));
  }

  /**
   * What is the length of the hedge (in meters)?
   */
  calculateLength() {
    let length = 0;
    for (let i = 0; i < this.latLngs.length - 1; i++) {
      length += this.latLngs[i].distanceTo(this.latLngs[i + 1]);
    }
    return length;
  }

  updateLength() {
    this.latLngs = this.polyline.getLatLngs();
    this.length = this.calculateLength();
  }

  handleMouseOver() {
    this.isHovered = true;
    this.polyline.setStyle(hoveredStyle);
    if (this.polyline._path) {
      this.polyline._path.classList.add("hovered");
    }
  }

  handleMouseOut() {
    this.isHovered = false;
    this.polyline.setStyle(normalStyle);
    if (this.polyline._path) {
      this.polyline._path.classList.remove("hovered");
    }
  }

  centerOnMap() {
    const bounds = this.polyline.getBounds();
    this.map.fitBounds(bounds, { padding: [25, 25] });
  }

  remove() {
    this.polyline.remove();
    this.onRemove(this);
  }
}


createApp({

  // Prevent conflict with django template delimiters
  delimiters: ["[[", "]]"],

  setup() {
    const hedges = reactive([]);
    let map = null;
    let nextId = ref(0);

    // Convert an array index into a string identifier (A, B, …, AA, AB, …)
    const getAlphaIdentifier = (index) => {
      let str = '';
      while (index >= 0) {
        str = String.fromCharCode((index % 26) + 65) + str;
        index = Math.floor(index / 26) - 1;
      }
      return str;
    };

    // Update all hedges identifiers (since they always must be in order)
    const updateHedgeIds = () => {
      hedges.forEach((hedge, index) => {
        hedge.id = getAlphaIdentifier(index);
      });
    };

    // Create a new hedge object
    const startDrawing = () => {
      const hedgeId = getAlphaIdentifier(nextId.value++);
      const hedge = reactive(new Hedge(map, hedgeId, removeHedge));
      hedge.init();
      hedges.push(hedge);
    };

    // Remove hedge from the object
    // This method is called as a callback from the Hedge object itself
    const removeHedge = (hedge) => {
      let index = hedges.indexOf(hedge);
      hedges.splice(index, 1);
      updateHedgeIds();
      nextId.value = hedges.length;
    };

    // Center the map around all existing hedges
    const zoomOut = () => {
      if (hedges.length > 0) {
        const group = new L.featureGroup(hedges.map(p => p.polyline));
        map.fitBounds(group.getBounds(), fitBoundsOptions);
      }
    };

    // Mount the app component and initialize the leaflet map
    onMounted(() => {
      map = L.map('map', {
        editable: true,
        doubleClickZoom: false,
      }).setView([43.6861, 3.5911], 17);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
      }).addTo(map);
    });

    return {
      hedges,
      startDrawing,
      removeHedge,
      zoomOut,
    };
  }
}).mount('#app');
