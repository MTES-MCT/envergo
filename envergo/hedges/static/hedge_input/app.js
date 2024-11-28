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
  init(latLngs = [], additionalData = {}) {
    // this.polyline = L.polyline(latLngs || [], styles[type].normal);
    // this.polyline.addTo(map);
    // this.polyline.enableEdit(map);
    // this.polyline.editor.continueForward();

    this.polyline = this.map.editTools.startPolyline(null, styles[this.type].normal);
    if (latLngs.length > 0) {
      this.polyline.editor.connect();
      latLngs.forEach((latLng) => this.polyline.editor.push(latLng));
      this.polyline.editor.endDrawing();
    }
    this.additionalData = additionalData;

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
      additionalData: this.additionalData,
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

  addHedge(map, onRemove, latLngs = [], additionalData = {}) {
    const hedgeId = this.getIdentifier(this.nextId.value++);
    const hedge = reactive(new Hedge(map, hedgeId, this.type, onRemove));
    hedge.init(latLngs, additionalData);
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
    // P for "planter", D for "détruire"
    let firstLetter = this.type === TO_PLANT ? 'P' : 'D';
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

    const addHedge = (type, latLngs = [], additionalData = {}) => {
      let hedgeList = hedges[type];
      let onRemove = hedgeList.removeHedge.bind(hedgeList);
      const newHedge = hedgeList.addHedge(map, onRemove, latLngs, additionalData);

      newHedge.polyline.on('editable:vertex:new', () => {
        showHelpBubble.value = true;
      });

      // Cacher la bulle d'aide à la fin du tracé
      newHedge.polyline.on('editable:drawing:end', () => {
        showHelpBubble.value = false;
        showHedgeModal(newHedge);
      });

      return newHedge;
    };

    // Show the "description de la haie" form modal
    const showHedgeModal = (hedge) => {
      const dialog = document.getElementById("hedge-data-dialog");
      const form = dialog.querySelector("form");
      const hedgeTypeField = document.getElementById("id_hedge_type");
      const pacField = document.getElementById("id_sur_parcelle_pac");
      const nearPondField = document.getElementById("id_proximite_mare");
      const hedgeName = document.getElementById("hedge-data-dialog-hedge-name");
      const hedgeLength = document.getElementById("hedge-data-dialog-hedge-length");

      // Pre-fill the form with hedge data if it's an edition
      if (hedge.additionalData) {
        hedgeTypeField.value = hedge.additionalData.typeHaie;
        pacField.checked = hedge.additionalData.surParcellePac;
        nearPondField.checked = hedge.additionalData.proximiteMare;
      } else {
        form.reset();
      }
      hedgeName.textContent = hedge.id;
      hedgeLength.textContent = hedge.length.toFixed(0);

      // Save form data to the hedge object
      // This is the form submit event handler
      const saveModalData = (event) => {
        event.preventDefault();

        const hedgeType = hedgeTypeField.value;
        const isOnPacField = pacField.checked;
        const isNearPond = nearPondField.checked;
        hedge.additionalData = {
          typeHaie: hedgeType,
          surParcellePac: isOnPacField,
          proximiteMare: isNearPond,
        };

        // Reset the form and hide the modal
        form.reset();
        dsfr(dialog).modal.conceal();
      };


      // Save data upon form submission
      form.addEventListener("submit", saveModalData, { once: true });

      // If the modal is closed without saving, let's make sure to remove the
      // event listener.
      dialog.addEventListener("dsfr.conceal", () => {
        form.removeEventListener("submit", saveModalData);
      });

      dsfr(dialog).modal.disclose();
    };

    // Open the form modal to edit an existing hedge
    const editHedge = (hedge) => {
      showHedgeModal(hedge);
    };

    const startDrawingToPlant = () => {
      return addHedge(TO_PLANT);
    };

    const startDrawingToRemove = () => {
      return addHedge(TO_REMOVE);
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

    const saveUrl = document.getElementById('app').dataset.saveUrl;

    // Persist data to the server
    const saveData = () => {
      const hedgesToPlant = hedges[TO_PLANT].toJSON();
      const hedgesToRemove = hedges[TO_REMOVE].toJSON();
      const hedgesData = hedgesToPlant.concat(hedgesToRemove);
      fetch(saveUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(hedgesData),
      })
        .then((response) => response.json())
        .then((data) => {
          console.log('Data saved with ID:', data.input_id);
          window.parent.postMessage(data);
        })
        .catch((error) => console.error('Error:', error));
    };

    const cancel = () => {
      window.parent.postMessage({ action: 'cancel' });
    }

    const savedHedgesData = JSON.parse(document.getElementById('app').dataset.hedgesData);

    /**
     * Restore hedges for existing inputs.
     */
    const restoreHedges = () => {
      savedHedgesData.forEach(hedgeData => {
        const type = hedgeData.type;
        const latLngs = hedgeData.latLngs.map((latlng) => L.latLng(latlng));
        const additionalData = hedgeData.additionalData;

        // We don't restore ids, but since we restore hedges in the same order
        // they were created, they should get the correct ids anyway.
        const hedge = addHedge(type, latLngs, additionalData);
      });
    };

    // Mount the app component and initialize the leaflet map
    onMounted(() => {
      const planLayer = L.tileLayer("https://data.geopf.fr/wmts?" +
        "&REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0" +
        "&STYLE=normal" +
        "&TILEMATRIXSET=PM" +
        "&FORMAT=image/png" +
        "&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2" +
        "&TILEMATRIX={z}" +
        "&TILEROW={y}" +
        "&TILECOL={x}", {
        maxZoom: 22,
        maxNativeZoom: 19,
        tileSize: 256,
        attribution: '&copy; <a href="https://www.ign.fr/">IGN</a>'
      });

      const satelliteLayer = L.tileLayer("https://data.geopf.fr/wmts?" +
        "&REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0" +
        "&STYLE=normal" +
        "&TILEMATRIXSET=PM" +
        "&FORMAT=image/jpeg" +
        "&LAYER=ORTHOIMAGERY.ORTHOPHOTOS" +
        "&TILEMATRIX={z}" +
        "&TILEROW={y}" +
        "&TILECOL={x}", {
        maxZoom: 22,
        maxNativeZoom: 19,
        tileSize: 256,
        attribution: '&copy; <a href="https://www.ign.fr/">IGN</a>'
      });

      // Display layer switching control
      const baseMaps = {
        "Plan": planLayer,
        "Satellite": satelliteLayer
      };

      map = L.map('map', {
        editable: true,
        doubleClickZoom: false,
        zoomControl: false,
        layers: [satelliteLayer]
      });

      L.control.layers(baseMaps, null, { position: 'bottomleft' }).addTo(map);

      L.control.zoom({
        position: 'bottomright'
      }).addTo(map);

      // Zoom on the selected address
      window.addEventListener('EnvErgo:citycode_selected', function (event) {
        const coordinates = event.detail.coordinates;
        const latLng = [coordinates[1], coordinates[0]];
        let zoomLevel = 19;
        map.setView(latLng, zoomLevel);
      });

      // Here, we want to restore existing hedges
      // If there are any, set view to see them all
      // Otherwise, set a default view with a zoom level of 14
      // There is a catch though. If we set a zoom level of 14 in the
      // first `setView` call, it triggers a bug with hedges polylines middle
      // markers that are displayed outside of the actual line. That's because
      // the marker positions are calculated with a precision that is dependant
      // on the zoom level.
      // So we have to set the view with a zoom maxed out, restore the markers,
      // then zoom out.
      map.setView([43.6861, 3.5911], 22);
      restoreHedges();
      map.setZoom(14);
      zoomOut();
    });

    return {
      hedges,
      compensationRate,
      startDrawingToPlant,
      startDrawingToRemove,
      zoomOut,
      showHelpBubble,
      saveData,
      cancel,
      editHedge,
    };
  }
}).mount('#app');
