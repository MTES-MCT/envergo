(function(exports, L) {
  'use strict';

  /**
   * Settings and behavior for the moulinette form map widget.
   */
  const MoulinetteMap = function() {
    this.configureLeaflet();
    this.map = this.initializeMap();
    this.marker = this.initializeMarker();
    this.marker.addTo(this.map);
    this.map.panTo(this.marker.getLatLng());
    this.registerEvents();
  };
  exports.MoulinetteMap = MoulinetteMap;


  /**
   * Set up leaflet options and translation strings.
   */
  MoulinetteMap.prototype.configureLeaflet = function() {
    L.drawLocal.draw.toolbar.buttons.marker = 'Cliquer pour placer un marqueur';
    L.drawLocal.draw.handlers.marker.tooltip.start = 'Cliquez pour placer le marqueur';
    L.drawLocal.draw.toolbar.actions.text = 'Annuler';
  };

  /**
   * Create and initialize the leaflet map and add default layers.
   */
  MoulinetteMap.prototype.initializeMap = function() {
    const map = L.map('map', { maxZoom: 21, }).setView(DEFAULT_LAT_LNG, 15);
    map.doubleClickZoom.disable();

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 22,
      maxNativeZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
    }).addTo(map);

    return map;
  };

  /**
   * Create the main marker object that is manipulated by the widget.
   */
  MoulinetteMap.prototype.initializeMarker = function(map) {
    const options = {
      draggable: true,
      autoPan: true,
    };

    const marker = L.marker(DEFAULT_LAT_LNG, options);
    return marker;
  };

  MoulinetteMap.prototype.setMarkerPosition = function(latLng) {
    this.marker.setLatLng(latLng);
    this.map.panTo(latLng);
  };

  MoulinetteMap.prototype.setFieldValue = function(latLng) {
    var latField = document.getElementById(LAT_FIELD_ID);
    latField.value = latLng.lat.toFixed(5);
    var lngField = document.getElementById(LNG_FIELD_ID);
    lngField.value = latLng.lng.toFixed(5);
  };

  MoulinetteMap.prototype.registerEvents = function() {

    /**
     * Double-clicking must move the marker around
     * (instead of the classic "zooming" behaviour.
     */
    this.map.on('dblclick', function(event) {
      L.DomEvent.preventDefault(event);
      const latLng = event.latlng;
      this.setMarkerPosition(latLng);
    }.bind(this));

    /**
     * This event is called whenever the marker has been moved.
     * (via double-click, dragging, etc.
     */
    this.marker.on('move', function(event) {
      const latLng = event.latlng;
      this.setFieldValue(latLng);
    }.bind(this));

    /**
     * Center the map on the marker after dragging.
     */
    this.marker.on('moveend', function(event) {
      const latLng = event.target.getLatLng();
      this.map.panTo(latLng);
    }.bind(this));

  };

})(this, L);


(function() {
  let moulinetteMap;

  window.addEventListener('load', function() {
    moulinetteMap = new MoulinetteMap();
  });

  window.addEventListener('EnvErgo:citycode_selected', function(event) {
    const coordinates = event.detail.coordinates;
    const latLng = [coordinates[1], coordinates[0]];
    moulinetteMap.setMarkerPosition(latLng);
    // map.setView(latLng, 19)
  });
})();
