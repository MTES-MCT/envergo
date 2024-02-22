(function (exports, L) {
  'use strict';

  /**
   * Settings and behavior for the moulinette form map widget.
   */
  const Map = function (options) {
    this.options = options;
    this.configureLeaflet();
    this.map = this.initializeMap();
    this.marker = this.initializeMarker();

    if (this.options.displayMarker) {
      this.marker.addTo(this.map);
    }

    this.registerEvents();
  };
  exports.Map = Map;


  /**
   * Set up leaflet options and translation strings.
   */
  Map.prototype.configureLeaflet = function () {
    L.drawLocal.draw.toolbar.buttons.marker = 'Cliquer pour placer un marqueur';
    L.drawLocal.draw.handlers.marker.tooltip.start = 'Cliquez pour placer le marqueur';
    L.drawLocal.draw.toolbar.actions.text = 'Annuler';
  };

  /**
   * Create and initialize the leaflet map and add default layers.
   */
  Map.prototype.initializeMap = function () {
    const map = L.map('map', {
      maxZoom: 21,
    }).setView(this.options.centerMap, this.options.defaultZoom);
    map.doubleClickZoom.disable();

    L.tileLayer("https://wxs.ign.fr/essentiels/geoportail/wmts?" +
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
    }).addTo(map);

    return map;
  };

  /**
   * Create the main marker object that is manipulated by the widget.
   */
  Map.prototype.initializeMarker = function (map) {
    // Bypass an issue with leaflet detecting a bad icon url, caused by
    // assets versioning
    L.Icon.Default.prototype.options.imagePath = '/static/leaflet/images/';

    const options = {
      draggable: true,
      autoPan: true,
    };

    const marker = L.marker(this.options.centerMap, options);
    return marker;
  };

  Map.prototype.setMarkerPosition = function (latLng, zoomLevel) {

    if (!this.map.hasLayer(this.marker)) {
      this.marker.addTo(this.map);
    }

    this.marker.setLatLng(latLng);
    this.map.setView(latLng, zoomLevel);

    const event = new CustomEvent('EnvErgo:map_marker_moved', { detail: latLng });
    window.dispatchEvent(event);
  };

  Map.prototype.setFieldValue = function (latLng) {
    var latField = document.getElementById(this.options.latFieldId);
    latField.value = latLng.lat.toFixed(5);
    var lngField = document.getElementById(this.options.lngFieldId);
    lngField.value = latLng.lng.toFixed(5);
  };

  Map.prototype.registerEvents = function () {

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

})(this, L);


(function () {
  let map;

  window.addEventListener('load', function () {
    const options = {
      displayMarker: DISPLAY_MARKER,
      centerMap: CENTER_MAP,
      defaultZoom: DEFAULT_ZOOM,
      latFieldId: LAT_FIELD_ID,
      lngFieldId: LNG_FIELD_ID,
    }
    map = new Map(options);
  });
})();
