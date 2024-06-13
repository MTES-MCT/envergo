(function (exports, L, _paq) {
  'use strict';

  // Prevent scrolling to the map when clicking on the zoom button
  // See https://stackoverflow.com/questions/57184529/how-to-prevent-leaflet-from-scrolling-the-page-when-clicking-the-zoom-buttons/57186116#57186116
  L.Control.prototype._refocusOnMap = function _refocusOnMap(ev) {
    // if map exists and event is not a keyboard event
    if (this._map && ev && ev.screenX > 0 && ev.screenY > 0) {
      this._map.getContainer().focus({ preventScroll: true });
    }
  };

  /**
   * Settings and behavior for the moulinette form map widget.
   */
  const MoulinetteMap = function (options) {
    this.options = options;
    this.configureLeaflet();
    this.map = this.initializeMap();
    this.marker = this.initializeMarker();
    this.initialLatLng = this.marker.getLatLng();

    if (this.options.displayMarker) {
      this.marker.addTo(this.map);
    }

    if (this.options.isStatic) {
      this.disableHandlers();
    } else {
      this.registerEvents();
    }

    this.setupAnalytics();
  };
  exports.MoulinetteMap = MoulinetteMap;


  /**
   * Set up leaflet options and translation strings.
   */
  MoulinetteMap.prototype.configureLeaflet = function () {
    L.drawLocal.draw.toolbar.buttons.marker = 'Cliquer pour placer un marqueur';
    L.drawLocal.draw.handlers.marker.tooltip.start = 'Cliquez pour placer le marqueur';
    L.drawLocal.draw.toolbar.actions.text = 'Annuler';
  };

  /**
   * Create and initialize the leaflet map and add default layers.
   */
  MoulinetteMap.prototype.initializeMap = function () {
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

    const map = L.map('map', {
      maxZoom: 21,
      scrollWheelZoom: this.options.isStatic ? 'center' : true,
      layers: [planLayer],
    }).setView(this.options.centerMap, this.options.defaultZoom);
    map.doubleClickZoom.disable();

    const baseMaps = {
      "Plan": planLayer,
      "Satellite": satelliteLayer
    };

    const layerControl = L.control.layers(baseMaps);
    layerControl.addTo(map);

    return map;
  };

  /**
   * Create the main marker object that is manipulated by the widget.
   */
  MoulinetteMap.prototype.initializeMarker = function (map) {
    // Bypass an issue with leaflet detecting a bad icon url, caused by
    // assets versioning
    L.Icon.Default.prototype.options.imagePath = '/static/leaflet/images/';

    const options = {
      draggable: !this.options.isStatic,
      autoPan: true,
    };

    const marker = L.marker(this.options.centerMap, options);
    return marker;
  };

  MoulinetteMap.prototype.setMarkerPosition = function (latLng, zoomLevel) {

    if (!this.map.hasLayer(this.marker)) {
      this.marker.addTo(this.map);
    }

    this.marker.setLatLng(latLng);
    this.map.setView(latLng, zoomLevel);

    const event = new CustomEvent('EnvErgo:map_marker_moved', { detail: latLng });
    window.dispatchEvent(event);
  };

  MoulinetteMap.prototype.setFieldValue = function (latLng) {
    var latField = document.getElementById(this.options.latFieldId);
    latField.value = latLng.lat.toFixed(5);
    var lngField = document.getElementById(this.options.lngFieldId);
    lngField.value = latLng.lng.toFixed(5);
  };

  MoulinetteMap.prototype.disableHandlers = function () {
    this.map.dragging.disable();
    this.map.keyboard.disable();
  };

  MoulinetteMap.prototype.registerEvents = function () {

    /**
     * Double-clicking must move the marker around
     * (instead of the classic "zooming" behaviour.
     */
    this.map.on('dblclick', function (event) {

      L.DomEvent.preventDefault(event);
      const latLng = event.latlng;
      this.setMarkerPosition(latLng);

      const newEvent = new CustomEvent('EnvErgo:map_dbl_clicked', { detail: latLng });
      window.dispatchEvent(newEvent);

    }.bind(this));

    /**
     * This event is called whenever the marker has been moved.
     * (via double-click, dragging, etc.
     */
    this.marker.on('move', function (event) {
      const latLng = event.latlng;
      this.setFieldValue(latLng);
    }.bind(this));

    /**
     * Center the map on the marker after dragging.
     */
    this.marker.on('moveend', function (event) {
      const latLng = event.target.getLatLng();
      this.map.panTo(latLng);
    }.bind(this));

  };

  MoulinetteMap.prototype.setupAnalytics = function () {
    this.map.on('baselayerchange', function (e) {
      // This script is called to display the map on both the moulinette form,
      // and the eval result page, but we need to trigger different analytics
      // events when the map layer is changed
      switch (this.options.mapType) {
        case "Content":
          _paq.push(['trackEvent', "Content", 'LocationMapSwitchLayer', e.name]);
          break;
        case "Form":
          _paq.push(['trackEvent', "Form", 'MapSwitchLayer', e.name]);
          break;
      }
    }.bind(this));
  };

  MoulinetteMap.prototype.reset = function () {
    this.setMarkerPosition(this.initialLatLng);
  };

})(this, L, window._paq);


(function () {
  let moulinetteMap;

  window.addEventListener('load', function () {
    const options = {
      displayMarker: DISPLAY_MARKER,
      centerMap: CENTER_MAP,
      defaultZoom: DEFAULT_ZOOM,
      latFieldId: LAT_FIELD_ID,
      lngFieldId: LNG_FIELD_ID,
      isStatic: IS_MAP_STATIC,
      mapType: MAP_TYPE,
    }
    moulinetteMap = new MoulinetteMap(options);
  });

  window.addEventListener("pageshow", function (event) {
    // This event occur when the user navigates back, and the page is
    // rendered from cache.
    // In that case, we want to display the initial marker position,
    // so the widget map and the result maps are in sync.
    // The "pageshow" event fires after the "load" event, so the map is
    // already initialized.
    if (event.persisted) {
      moulinetteMap.reset();
    }
  });

  window.addEventListener('EnvErgo:citycode_selected', function (event) {
    const coordinates = event.detail.coordinates;
    const latLng = [coordinates[1], coordinates[0]];

    // When an address is selected, place a marker and zoom on it
    let zoomLevel = 19;
    moulinetteMap.setMarkerPosition(latLng, zoomLevel);
  });
})();
