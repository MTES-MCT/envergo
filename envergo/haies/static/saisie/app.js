const { createApp, ref, onMounted, reactive } = Vue

const TO_PLANT = 'TO_PLANT';
const TO_REMOVE = 'TO_REMOVE';

// Those styles are overidden by the CSS file
const styles = {
  TO_PLANT: {
    normal: { color: 'green', className: 'hedge to-plant' },
    hovered: { color: 'darkgreen' },
  },
  TO_REMOVE: {
    normal: { color: 'red', className: 'hedge to-remove' },
    hovered: { color: 'darkred' },
  },
};
const fitBoundsOptions = { padding: [25, 25] };



/**
 * Represent a single hedge object.
 *
 * @param {L.Map} map - The Leaflet map object.
 * @param {string} id - The identifier of the hedge (A, B, …, AA, AB, …).
 * @param {string} type - The type of the hedge (TO_PLANT, TO_REMOVE).
 * @param {function} onRemove - The callback function to call when the hedge is removed.
 */
class Hedge {
  constructor(map, id, type, onRemove) {
    this.id = id;
    this.map = map;
    this.type = type;
    this.onRemove = onRemove;
    this.polyline = map.editTools.startPolyline(null, styles[type].normal);
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
    this.polyline.setStyle(styles[this.type].hovered);
    if (this.polyline._path) {
      this.polyline._path.classList.add("hovered");
    }
  }

  handleMouseOut() {
    this.isHovered = false;
    this.polyline.setStyle(styles[this.type].normal);
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
    let map = null;
    const hedges = {
      TO_PLANT: reactive([]),
      TO_REMOVE: reactive([])
    };
    const nextId = {
      TO_PLANT: ref(0),
      TO_REMOVE: ref(0),
    };

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
    const updateHedgeIds = (hedges) => {
      hedges.forEach((hedge, index) => {
        hedge.id = getAlphaIdentifier(index);
      });
    };

    // Create a new hedge object
    const startDrawing = (type) => {
      const hedgeId = getAlphaIdentifier(nextId[type].value++);
      const hedge = reactive(new Hedge(map, hedgeId, type, removeHedge));
      hedge.init();
      hedges[type].push(hedge);
    };

    const startDrawingToPlant = () => {
      return startDrawing(TO_PLANT);
    };

    const startDrawingToRemove = () => {
      return startDrawing(TO_REMOVE);
    };

    // Remove hedge from the object
    // This method is called as a callback from the Hedge object itself
    const removeHedge = (hedge) => {
      let type = hedge.type;
      let index = hedges[type].indexOf(hedge);
      hedges[type].splice(index, 1);
      updateHedgeIds(hedges[type]);
      nextId[type].value = hedges[type].length;
    };

    // Center the map around all existing hedges
    const zoomOut = () => {
      // The concat method does not modify the original arrays
      let allHedges = hedges[TO_REMOVE].concat(hedges[TO_PLANT]);
      if (allHedges.length > 0) {
        const group = new L.featureGroup(allHedges.map(p => p.polyline));
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
      startDrawingToPlant,
      startDrawingToRemove,
      removeHedge,
      zoomOut,
    };
  }
}).mount('#app');
