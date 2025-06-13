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
    if (this.options.debug) {
      this.drawEnvelope();
    }
    this.drawPolygons();
    this.addLegend();
    this.addControl();
    this.addScaleControl();

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

    L.tileLayer("https://data.geopf.fr/private/wmts?" +
      "apikey=ign_scan_ws" +
      "&REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0" +
      "&STYLE=normal" +
      "&TILEMATRIXSET=PM" +
      "&FORMAT=image/jpeg" +
      "&LAYER=GEOGRAPHICALGRIDSYSTEMS.MAPS.SCAN25TOUR" +
      "&TILEMATRIX={z}" +
      "&TILEROW={y}" +
      "&TILECOL={x}", {
      maxZoom: 22,
      maxNativeZoom: 16,
      tileSize: 256,
      attribution: '&copy; <a href="https://www.ign.fr/">IGN</a>'
    }).addTo(map);

    return map;
  };

  /**
   * Create the main marker object that is manipulated by the widget.
   */
  Map.prototype.initializeMarker = function (map) {

    const options = {
      draggable: true,
      autoPan: true,
    };

    const marker = L.marker(this.options.centerMap, options);
    return marker;
  };

  Map.prototype.drawPolygons = function () {

    var style = function (polygon) {
      return {
        fillColor: getColor(polygon.properties.value),
        weight: 2,
        opacity: 1,
        color: 'white',
        dashArray: '3',
        fillOpacity: 0.7
      };
    };

    var onEachFeature = function (feature, layer) {
      layer.on({
        mouseover: this.highlightFeature.bind(this),
        mouseout: this.resetHighlight.bind(this),
      });
    };

    if (this.options.polygons) {
      var features = this.options.polygons.map(function (polygon) {
        var polygonJSON = {
          type: "Feature",
          properties: { value: polygon[2] },
          geometry: JSON.parse(polygon[3])
        };
        return polygonJSON;
      });

      var geoJSON = L.geoJSON(
        {
          type: "FeatureCollection",
          features: features,
        },
        { style: style, onEachFeature: onEachFeature.bind(this) });

      geoJSON.addTo(this.map);
    }
  };

  Map.prototype.drawEnvelope = function () {
    if (this.options.envelope) {
      var envelope = JSON.parse(this.options.envelope);
      var style = {
        weight: 2,
        opacity: 1,
        color: 'black',
        fillOpacity: 0,
      };
      L.geoJSON(envelope, { style: style }).addTo(this.map);
    }
  };

  Map.prototype.highlightFeature = function (e) {

    var layer = e.target;
    layer.setStyle({
      weight: 5,
      color: '#666',
      dashArray: '',
      fillOpacity: 0.7
    });
    layer.bringToFront();
    this.info.update(layer.feature.properties);
  };

  Map.prototype.resetHighlight = function (e) {
    var layer = e.target;
    layer.setStyle({
      weight: 2,
      color: 'white',
      dashArray: '3',
      fillOpacity: 0.7
    });
    this.info.update();
  };

  Map.prototype.addLegend = function () {
    var legend = L.control({ position: 'bottomright' });
    legend.onAdd = function (map) {
      var div = L.DomUtil.create('div', 'info legend');

      this.options.legend.forEach((l) => {
        div.innerHTML +=
          '<i style="background:' + l.color + '"></i> ' + l.label;
      });

      return div;
    }.bind(this);
    legend.addTo(this.map);
  };

  Map.prototype.addControl = function () {
    this.info = L.control();

    this.info.onAdd = function (map) {
      this._div = L.DomUtil.create('div', 'info');
      this.update();
      return this._div;
    };

    // method that we will use to update the control based on feature properties passed
    this.info.update = function (props) {
      this._div.innerHTML = '<strong>Surface de bassin versant</strong><br />' + (props ?
        Math.floor(props.value) + ' m<sup>2</sup>'
        : '');
    };

    this.info.addTo(this.map);
  };

  Map.prototype.addScaleControl = function () {
    L.control.scale({ imperial: false }).addTo(this.map);
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
