import LatLon from '/static/geodesy/latlon-ellipsoidal-vincenty.js';

const { createApp, ref, onMounted, reactive, computed, watch } = Vue

const TO_PLANT = 'TO_PLANT';
const TO_REMOVE = 'TO_REMOVE';

const PLANTATION_MODE = 'plantation';
const REMOVAL_MODE = 'removal';
const READ_ONLY_MODE = 'read_only';

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

const mode = document.getElementById('app').dataset.mode;
const minimumLengthToPlant = parseFloat(document.getElementById('app').dataset.minimumLengthToPlant);
const conditionsUrl = document.getElementById('app').dataset.conditionsUrl;

/**
 * What is the length of the hedge (in meters)?
 *
 * We use Vincenty's solution on an ellipsoid model, to be as precise as
 * possible and coherent with the backend's side.
 */

const latLngsLength = (latLngs) => {
  let length = 0;
  for (let i = 0; i < latLngs.length - 1; i++) {
    const p1 = new LatLon(latLngs[i].lat, latLngs[i].lng);
    const p2 = new LatLon(latLngs[i + 1].lat, latLngs[i + 1].lng);
    length += p1.distanceTo(p2);
  }
  return length;
};

// Show the "description de la haie" form modal
const showHedgeModal = (hedge, hedgeType) => {

  const isReadonly = (
    mode === READ_ONLY_MODE ||
    (hedgeType === TO_PLANT && mode === REMOVAL_MODE) ||
    (hedgeType === TO_REMOVE && mode === PLANTATION_MODE)
  );
  const dialogMode = hedgeType === TO_PLANT ? PLANTATION_MODE : REMOVAL_MODE;

  const dialogId = `${dialogMode}-hedge-data-dialog`
  const dialog = document.getElementById(dialogId);
  const form = dialog.querySelector("form");
  const hedgeName = dialog.querySelector(".hedge-data-dialog-hedge-name");
  const hedgeLength = dialog.querySelector(".hedge-data-dialog-hedge-length");
  const resetForm = () => {
    form.reset();
    const inputs = form.querySelectorAll("input");
    const selects = form.querySelectorAll("select");

    inputs.forEach(input => input.disabled = false);
    selects.forEach(select => select.disabled = false);
    const submitButton = form.querySelector("button[type='submit']");
    submitButton.innerText = "Enregistrer";
  }

  resetForm();

  // Pre-fill the form with hedge data if it's an edition
  if (hedge.additionalData) {
    for (const property in hedge.additionalData) {
      const field = document.getElementById(`id_${dialogMode}-${property}`);
      if (field) {
        if (field.type === "checkbox") {
          field.checked = hedge.additionalData[property];
        } else if (field.type === "fieldset") {
          // radio group
          for (let i = 0; i < field.elements.length; i++) {
            let value = field.elements[i].value;
            if (value === hedge.additionalData[property]) {
              field.elements[i].checked = true
            }
          }
        } else {
          field.value = hedge.additionalData[property];
        }
      }
    }
  } else {
    form.reset();
  }
  hedgeName.textContent = hedge.id;
  hedgeLength.textContent = hedge.length.toFixed(0);

  // Save form data to the hedge object
  // This is the form submit event handler
  const saveModalData = (event) => {
    event.preventDefault();

    const form = event.target;

    for (const element of form.elements) {
      if (element instanceof HTMLInputElement ||
        element instanceof HTMLSelectElement ||
        element instanceof HTMLTextAreaElement) {
        // Skip buttons or inputs without a name
        if (!element.name || element.type === 'submit' || element.type === 'button') continue;

        const propertyName = element.name.split("-")[1]; // remove prefix
        if (element.type === "checkbox") {
          hedge.additionalData[propertyName] = element.checked;
        } else if (element.type === "radio") {
          if (element.checked) {
            hedge.additionalData[propertyName] = element.value;
          }
        }
        else {
          hedge.additionalData[propertyName] = element.value;
        }
      }
    }
    // Reset the form and hide the modal
    form.reset();
    dsfr(dialog).modal.conceal();
  };

  const closeModal = (event) => {
    event.preventDefault();
    // Hide the modal
    dsfr(dialog).modal.conceal();
  };

  if (isReadonly) {
    const inputs = form.querySelectorAll("input");
    const selects = form.querySelectorAll("select");

    inputs.forEach(input => input.disabled = true);
    selects.forEach(select => select.disabled = true);
    const submitButton = form.querySelector("button[type='submit']");
    submitButton.innerText = "Retour";

    form.addEventListener("submit", closeModal, { once: true });
  }
  else {
    // Save data upon form submission
    form.addEventListener("submit", saveModalData, { once: true });
  }

  // If the modal is closed without saving, let's make sure to remove the
  // event listener.
  dialog.addEventListener("dsfr.conceal", () => {
    form.removeEventListener("submit", saveModalData);
    hedge.isDrawingCompleted = true;
  });

  dsfr(dialog).modal.disclose();
};

function isTouchDevice() {
  return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
}


/**
 * Represent a single hedge object.
 *
 * @param {L.Map} map - The Leaflet map object.
 * @param {string} id - The identifier of the hedge (A, B, …, AA, AB, …).
 * @param {string} type - The type of the hedge (TO_PLANT, TO_REMOVE).
 * @param {function} onRemove - The callback function to call when the hedge is removed.
 */
class Hedge {
  constructor(map, id, type, onRemove, isDrawingCompleted) {
    this.id = id;
    this.map = map;
    this.type = type;
    this.onRemove = onRemove;
    this.isHovered = isTouchDevice(); // On touch devices, consider the hover state as always true
    this.isDrawingCompleted = isDrawingCompleted;

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

    this.updateProperties();
    if (mode !== READ_ONLY_MODE) {
      this.polyline.on('editable:vertex:new', this.updateProperties.bind(this));
      this.polyline.on('editable:vertex:deleted', this.updateProperties.bind(this));
      this.polyline.on('editable:vertex:dragend', this.updateProperties.bind(this));
    } else {
      this.polyline.disableEdit();
    }
    this.polyline.on('click', () => showHedgeModal(this, this.type));
    this.polyline.on('mouseover', this.handleMouseOver.bind(this));
    this.polyline.on('mouseout', this.handleMouseOut.bind(this));

    // add a hitbox polyline around the main polyline to improve accessibility
    this.hitbox = L.polyline(latLngs, {
      color: 'transparent',
      weight: 20, // invisible but wide click zone
      className: 'hedge-hitbox',
      interactive: true,
      bubblingMouseEvents: false,
    }).addTo(this.map);

    // Keep the hitbox geometry in sync with the main polyline
    ['editable:vertex:new', 'editable:vertex:deleted', 'editable:vertex:dragend', 'editable:editing']
      .forEach((evt) => {
        this.polyline.on(evt, () => this.syncHitbox());
      });

    // --- Forward interaction events from hitbox → main polyline
    ['click', 'mouseover', 'mouseout'].forEach((ev) => {
      this.hitbox.on(ev, (e) => this.polyline.fire(ev, e));
    });

    // hide hedges to plant on removal mode
    if (this.type === TO_PLANT && mode === REMOVAL_MODE) {
      this.map.removeLayer(this.hitbox);
      this.map.removeLayer(this.polyline);
    }
  }

  syncHitbox() {
    if (this.hitbox && this.polyline) {
      this.hitbox.setLatLngs(this.polyline.getLatLngs())
    }
  }

  calculateLength() {
    return latLngsLength(this.latLngs);
  }

  updateProperties() {
    this.latLngs = this.polyline.getLatLngs();
    this.length = this.calculateLength();

    // Polyline box was only updated when expended, not shrinked
    // So we have to update it everytime
    // https://github.com/Leaflet/Leaflet.Editable/issues/110
    this.polyline._bounds = new L.LatLngBounds();
    this.latLngs.forEach((latLng) => {
      this.polyline._bounds.extend(latLng);
    });
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

  // Make sure all additional data is filled
  isValid() {
    const { type_haie } = this.additionalData;

    return type_haie !== undefined && type_haie && (!("position" in this.additionalData) || this.additionalData.position);
  }

  remove() {
    this.polyline.remove();
    this.hitbox.remove();
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

  *completelyDrawn() {
    for (let hedge of this.hedges) {
      if (hedge.isDrawingCompleted) {
        yield hedge;
      }
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

  get hasCompletedHedge() {
    return this.hedges.some(hedge => hedge.isDrawingCompleted);
  }

  addHedge(map, onRemove, latLngs = [], additionalData = {}, isDrawingCompleted = false) {
    const hedgeId = this.getIdentifier(this.nextId.value++);
    const hedge = reactive(new Hedge(map, hedgeId, this.type, onRemove, isDrawingCompleted));
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

function styleDrawGuide() {
  setTimeout(() => {
    const paths = document.querySelectorAll(".leaflet-zoom-animated g path:not(.hedge, .hedge-hitbox)");
    let drawGuide = paths.length ? paths[paths.length - 1] : null;
    if (drawGuide) {
      drawGuide.classList.add('leaflet-draw-guide')
    }
  }, 100); // Wait 100ms to let the element be created
}

createApp({
  /**
   * Create show and draw hedges app
   */

  // Prevent conflict with django template delimiters
  delimiters: ["[[", "]]"],

  setup() {
    let map = null;
    let tooltip = null;

    const hedges = {
      TO_PLANT: new HedgeList(TO_PLANT),
      TO_REMOVE: new HedgeList(TO_REMOVE),
    };

    const helpBubble = mode !== READ_ONLY_MODE ? ref("initialHelp") : ref(null);
    const hedgeBeingDrawn = ref(null);

    // Reactive properties for acceptability conditions
    const conditions = reactive({ status: 'loading', conditions: [] });

    // Computed property to track changes in the hedges array
    const hedgesToPlantSnapshot = computed(() => JSON.stringify(hedges[TO_PLANT].hedges.map(hedge => ({
      length: hedge.length,
      additionalData: hedge.additionalData
    }))));

    // Watch the computed property for changes
    watch(hedgesToPlantSnapshot, (newHedges, oldHedges) => {
      onHedgesToPlantChange();
    });

    const addHedge = (type, latLngs = [], additionalData = {}, isDrawingCompleted = false) => {
      let hedgeList = hedges[type];
      let onRemove = hedgeList.removeHedge.bind(hedgeList);
      return hedgeList.addHedge(map, onRemove, latLngs, additionalData, isDrawingCompleted);
    };

    const startDrawing = (type) => {
      helpBubble.value = "initHedgeHelp";
      const newHedge = addHedge(type);
      hedgeBeingDrawn.value = newHedge;

      newHedge.polyline.on('editable:vertex:new', (event) => {
        styleDrawGuide();

        if (event.vertex.getNext() === undefined) { // do not display tooltip when adding a point to an existing hedge
          helpBubble.value = "drawingHelp";
        }
      });

      newHedge.polyline.on('editable:drawing:end', onDrawingEnd);
      window.addEventListener('keyup', cancelDrawingFromEscape);

      return newHedge
    }

    const startDrawingToPlant = () => {
      return startDrawing(TO_PLANT);
    };

    const startDrawingToRemove = () => {
      return startDrawing(TO_REMOVE);
    };

    const stopDrawing = () => {
      removeTooltip();
      window.removeEventListener('keyup', cancelDrawingFromEscape);
      hedgeBeingDrawn.value = null;
      helpBubble.value = null;
    };

    const onDrawingEnd = () => {
      showHedgeModal(hedgeBeingDrawn.value, mode === PLANTATION_MODE ? TO_PLANT : TO_REMOVE);
      stopDrawing();
    };

    const cancelDrawing = () => {
      if (hedgeBeingDrawn.value) {
        hedgeBeingDrawn.value.polyline.off('editable:drawing:end', onDrawingEnd); // Remove the event listener
        hedgeBeingDrawn.value.remove();
        stopDrawing();
      }
    };

    const cancelDrawingFromEscape = (event) => {
      if (event.key === 'Escape') {
        cancelDrawing();
      }
    };


    // Center the map around all existing hedges
    const zoomOut = (animate = true) => {
      let allHedges = hedges[TO_REMOVE].hedges;
      if (mode !== REMOVAL_MODE) {
        allHedges = allHedges.concat(hedges[TO_PLANT].hedges);
      }
      // The concat method does not modify the original arrays
      if (allHedges.length > 0) {
        const group = new L.featureGroup(allHedges.map(p => p.polyline));
        map.fitBounds(group.getBounds(), { ...fitBoundsOptions, animate: animate, padding: [50, 50] });
      }
    };

    const saveUrl = document.getElementById('app').dataset.saveUrl;

    function serializeHedgesData() {
      const hedgesToPlant = hedges[TO_PLANT].toJSON();
      const hedgesToRemove = hedges[TO_REMOVE].toJSON();
      return hedgesToPlant.concat(hedgesToRemove);
    }

    // We first check if all hedges are valid
    const saveData = () => {
      const hedgesToValidate = mode === REMOVAL_MODE ? hedges[TO_REMOVE].hedges : hedges[TO_PLANT].hedges;
      const isValid = hedgesToValidate.every((hedge) => hedge.isValid());
      if (!isValid) {
        const dialog = document.getElementById("save-modal");
        dsfr(dialog).modal.disclose();

        // This hackish code is there to prevent a weird dsfr quirk
        // The dsfr modal is designed to be opened throught a button
        // Here, we use the js api to disclose the modal. If we add the
        // usual close button with the "aria-controls" attribute, the modal
        // just won't open. I've been banging my head for an entire day on this.
        const closeBtn = dialog.querySelector(".fr-btn--close");
        closeBtn.addEventListener("click", () => {
          dsfr(dialog).modal.conceal();
        }, "once");
      }
      else {
        const hedgesData = serializeHedgesData();
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
      }
    };

    // Cancel the input and return to the main form
    // We confirm with a modal if some hedges have been drawn
    const cancel = (event) => {
      const totalHedges = hedges[TO_PLANT].count + hedges[TO_REMOVE].count;
      if (totalHedges > 0 && mode !== READ_ONLY_MODE) {
        const dialog = document.getElementById("cancel-modal");
        const confirmCancel = document.getElementById("btn-quit-without-saving");
        const dismissCancel = document.getElementById("btn-back-to-map");

        const confirmHandler = () => {
          dsfr(dialog).modal.conceal();
          window.parent.postMessage({ action: 'cancel' });
        };

        const dismissHandler = () => {
          dsfr(dialog).modal.conceal();
          if (event && event.type === 'popstate') {
            history.pushState({ modalOpen: true }, "", "#modal");
          }
        };

        const concealHandler = () => {
          confirmCancel.removeEventListener("click", confirmHandler);
          dismissCancel.removeEventListener("click", dismissHandler);
        };

        confirmCancel.addEventListener("click", confirmHandler, { once: true });
        dismissCancel.addEventListener("click", dismissHandler, { once: true });
        dialog.addEventListener("dsfr.conceal", concealHandler, { once: true });

        dsfr(dialog).modal.disclose();
      } else {
        window.parent.postMessage({ action: 'cancel' });
      }
    }

    const savedHedgesData = JSON.parse(document.getElementById('app').dataset.hedgesData);

    /**
     * Restore hedges for existing inputs.
     */
    const restoreHedges = () => {
      if (savedHedgesData.length > 0) {
        helpBubble.value = null;
      }
      savedHedgesData.forEach(hedgeData => {
        const type = hedgeData.type;
        const latLngs = hedgeData.latLngs.map((latlng) => L.latLng(latlng));
        const additionalData = hedgeData.additionalData;

        // We don't restore ids, but since we restore hedges in the same order
        // they were created, they should get the correct ids anyway.
        const hedge = addHedge(type, latLngs, additionalData, true);
        if (type === TO_PLANT && mode === REMOVAL_MODE) {
          hedge.polyline.disableEdit();
        } else if (type === TO_REMOVE && mode === PLANTATION_MODE) {
          hedge.polyline.disableEdit();
        }
      });
    };

    const invalidHedges = computed(() => {
      const invalidHedges = hedges[mode === REMOVAL_MODE ? TO_REMOVE : TO_PLANT].hedges.filter((hedge) => !hedge.isValid());
      const invalidHedgesIds = invalidHedges.map((hedge) => hedge.id);
      const invalidHedgeList = invalidHedgesIds.join(', ');
      return invalidHedgeList;
    });

    const onHedgesToPlantChange = () => {

      // We don't need to update plantation conditions while an hedge is being
      // drawn, it's way too costly anyway
      if (hedgeBeingDrawn.value) return;

      conditions.status = "loading";

      // Prepare the hedge data to be sent in the request body
      const hedgeData = serializeHedgesData();

      fetch(conditionsUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify(hedgeData),
      })
        .then(response => response.json())
        .then(data => {
          // Note : using Object.assign will not delete keys.
          // E.g if the initial evaluation data has a `length_to_plant_pac` key,
          // and then an admin deactives the bcae8 regulation, the key will
          // not be present in the following requests, but the initial value
          // will remain in the current variable without ever being updated.
          Object.assign(conditions.conditions, data);
          conditions.status = "ok";
          conditions.result = conditions.conditions.every(element => element.result);
        })
        .catch(error => console.error('Error:', error));
    }

    const addTooltip = (e) => {
      if (tooltip.style.display == 'none') {
        tooltip.style.display = 'block';
      }
    }

    const removeTooltip = (e) => {
      tooltip.innerHTML = '';
      tooltip.style.display = 'none';
    }

    // Show the "hedge length" tooltip
    // There are two cases:
    //  1. we are drawing a new hedge
    //  2. we are editing an existing hedge by dragging a marker
    const updateTooltip = (e) => {
      let latLngs = null;;

      if (e.vertex) {
        latLngs = e.vertex.latlngs;
      } else if (hedgeBeingDrawn.value != null) {
        latLngs = [...hedgeBeingDrawn.value.polyline.getLatLngs()];
        latLngs.push(e.latlng);
      }

      if (latLngs) {
        tooltip.style.left = e.originalEvent.clientX - 10 + 'px';
        tooltip.style.top = e.originalEvent.clientY + 20 + 'px';
        let length = latLngsLength(latLngs);
        let totalLength = Math.ceil(length);
        tooltip.innerHTML = `${totalLength} m`;
      }
    }

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

      const pciLayer = L.tileLayer("https://data.geopf.fr/wmts?" +
        "&REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0" +
        "&STYLE=normal" +
        "&TILEMATRIXSET=PM" +
        "&FORMAT=image/png" +
        "&LAYER=CADASTRALPARCELS.PARCELLAIRE_EXPRESS" +
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

      const overlayMaps = {
        "Cadastre": pciLayer
      };

      map = L.map('map', {
        editable: true,
        doubleClickZoom: false,
        zoomControl: false,
        layers: [satelliteLayer, pciLayer]
      });
      tooltip = L.DomUtil.get('tooltip');

      L.control.layers(baseMaps, overlayMaps, { position: 'bottomleft' }).addTo(map);

      L.control.zoom({
        position: 'bottomright'
      }).addTo(map);

      // Remove helpBubbleMessage on zoom
      let isSetupDone = false;
      map.on('zoomend', () => {
        if (isSetupDone && helpBubble.value === "initialHelp") {
          helpBubble.value = null;
        }
      });

      // Zoom on the selected address
      window.addEventListener('Envergo:citycode_selected', function (event) {
        const coordinates = event.detail.coordinates;
        const latLng = [coordinates[1], coordinates[0]];
        let zoomLevel = 16;
        map.setView(latLng, zoomLevel);
        if (helpBubble.value === "initialHelp") {
          helpBubble.value = null;
        }
      });

      history.pushState({ modalOpen: true }, "", "#open-modal");
      window.addEventListener("popstate", cancel);

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

      if (mode === PLANTATION_MODE || mode === READ_ONLY_MODE) {
        // We need to call this function once to initialize the quality object
        onHedgesToPlantChange();
      }
      map.setZoom(14);
      zoomOut(false); // remove animation, it is smoother at the beginning, and it eases the helpBubbleMessage display

      map.on('editable:drawing:start', addTooltip);
      map.on('editable:drawing:end', removeTooltip);
      map.on('editable:vertex:dragstart', addTooltip);
      map.on('editable:vertex:dragend', removeTooltip);
      map.on("editable:drawing:move", updateTooltip);

      isSetupDone = true;
    });

    return {
      mode,
      hedges,
      startDrawingToPlant,
      startDrawingToRemove,
      zoomOut,
      helpBubble,
      saveData,
      cancel,
      showHedgeModal,
      invalidHedges,
      conditions,
      hedgeBeingDrawn,
      cancelDrawing,
    };
  }
}).mount('#app');
