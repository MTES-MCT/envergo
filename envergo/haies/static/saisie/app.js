const { createApp, ref, onMounted, reactive, computed } = Vue

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
const fitBoundsOptions = { padding: [10, 10] };



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

  toJSON() {
    return {
      id: this.id,
      latLngs: this.latLngs.map((latLng) => ({ lat: latLng.lat, lng: latLng.lng })),
      type: this.type,
    };
  }
}


/**
 * Encapsulate behaviour and properties for a list of hedges.
 *
 * @param {string} type - The type of the hedge list (TO_PLANT, TO_REMOVE).
 */
class HedgeList {
  constructor(type) {
    this.type = type;
    this.hedges = reactive([]);
    this.nextId = ref(0);
  }

  /**
   * Iterate on the hedge array
   *
   * This allows using `for (let hedge of hedges) { … }` syntax where `hedges`
   * is an instance of `HedgeList`.
   *
   * (I hate this stupid syntax)
   */
  *[Symbol.iterator]() {
    for (let hedge of this.hedges) {
      yield hedge;
    }
  }

  /**
   * Return the total length of all hedges (in meters) in the list.
   */
  get totalLength() {
    return this.hedges.reduce((total, hedge) => total + hedge.length, 0);
  }

  /**
   * Return the number of hedges in the list.
   */
  get count() {
    return this.hedges.length;
  }

  addHedge(map, onRemove) {
    const hedgeId = this.getIdentifier(this.nextId.value++);
    const hedge = reactive(new Hedge(map, hedgeId, this.type, onRemove));
    hedge.init();
    this.hedges.push(hedge);

    return hedge;
  }

  removeHedge(hedge) {
    let index = this.hedges.indexOf(hedge);
    this.hedges.splice(index, 1);
    this.updateHedgeIds();
    this.nextId.value = this.hedges.length;
  }

  getIdentifier(index) {
    // P for "planter", A for "arracher"
    let firstLetter = this.type === TO_PLANT ? 'P' : 'A';
    let identifier = `${firstLetter}${index + 1}`;
    return identifier;
  }

  updateHedgeIds() {
    this.hedges.forEach((hedge, index) => {
      hedge.id = this.getIdentifier(index);
    });
  }

  toJSON() {
    return this.hedges.map((hedge) => hedge.toJSON());
  }
}

createApp({

  // Prevent conflict with django template delimiters
  delimiters: ["[[", "]]"],

  setup() {
    let map = null;
    const hedges = {
      TO_PLANT: new HedgeList(TO_PLANT),
      TO_REMOVE: new HedgeList(TO_REMOVE),
    };
    const compensationRate = computed(() => {
      let toPlant = hedges[TO_PLANT].totalLength;
      let toRemove = hedges[TO_REMOVE].totalLength;
      return toRemove > 0 ? toPlant / toRemove * 100 : 0;
    });
    const showHelpBubble = ref(false);

    const startDrawing = (type) => {
      let hedgeList = hedges[type];
      let onRemove = hedgeList.removeHedge.bind(hedgeList);
      const newHedge = hedgeList.addHedge(map, onRemove);

      newHedge.polyline.on('editable:vertex:new', () => {
        showHelpBubble.value = true;
      });

      // Cacher la bulle d'aide à la fin du tracé
      newHedge.polyline.on('editable:drawing:end', () => {
        showHelpBubble.value = false;
      });
    };

    const startDrawingToPlant = () => {
      return startDrawing(TO_PLANT);
    };

    const startDrawingToRemove = () => {
      return startDrawing(TO_REMOVE);
    };



    // Center the map around all existing hedges
    const zoomOut = () => {
      // The concat method does not modify the original arrays
      let allHedges = hedges[TO_REMOVE].hedges.concat(hedges[TO_PLANT].hedges);
      if (allHedges.length > 0) {
        const group = new L.featureGroup(allHedges.map(p => p.polyline));
        map.fitBounds(group.getBounds(), fitBoundsOptions);
      }
    };

    const saveData = () => {
      const hedgesData = {
        TO_PLANT: hedges[TO_PLANT].toJSON(),
        TO_REMOVE: hedges[TO_REMOVE].toJSON(),
      };
      console.log(hedgesData);
      // fetch('/api/save-hedges/', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(hedgesData),
      // });
    };

    // Mount the app component and initialize the leaflet map
    onMounted(() => {
      map = L.map('map', {
        editable: true,
        doubleClickZoom: false,
        zoomControl: false,
      }).setView([43.6861, 3.5911], 17);

      L.control.zoom({
        position: 'bottomright'
      }).addTo(map);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
      }).addTo(map);
    });

    return {
      hedges,
      compensationRate,
      startDrawingToPlant,
      startDrawingToRemove,
      zoomOut,
      showHelpBubble,
      saveData,
    };
  }
}).mount('#app');
