(function (exports, L, _paq) {
  'use strict';

  /**
   * Initialize the leaflet maps for the moulinette result page.
   */
  const MapConfigurator = function (maps) {
    this.maps = maps;
  };
  exports.MapConfigurator = MapConfigurator;

  MapConfigurator.prototype.init = function () {
    for (const map in this.maps) {
      this.initMap(map);
    };
  };

  MapConfigurator.prototype.initMap = function (mapId) {
    const mapData = this.maps[mapId];
    const center = mapData.center;

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

    // Damn this constant lat and lng order mixing
    const centerCoords = [center.coordinates[1], center.coordinates[0]];
    const map = L.map(mapId, {
      maxZoom: 21,
      zoomControl: !mapData["fixed"],
      dragging: !mapData["fixed"],
      doubleClickZoom: !mapData["fixed"],
      scrollWheelZoom: !mapData["fixed"],
      touchZoom: !mapData["fixed"],
      keyboard: !mapData["fixed"],
      layers: [planLayer],
    }).setView(centerCoords, mapData['zoom']);

    // Display layer switching control
    const baseMaps = {
      "Plan": planLayer,
      "Satellite": satelliteLayer
    };

    const layerControl = L.control.layers(baseMaps);
    layerControl.addTo(map);

    // Display the project's coordinates as a maker
    const marker = L.marker(centerCoords);
    marker.addTo(map);

    // Display all polygons
    const bounds = L.latLngBounds();
    for (const polygonId in mapData.polygons) {
      const polygon = mapData.polygons[polygonId];
      const polygonJson = L.geoJSON(
        polygon['polygon'], { style: { color: polygon['color'], fillColor: polygon['color'] } });
      bounds.extend(polygonJson.getBounds());
      polygonJson.addTo(map);
    }

    if (mapData["zoom"] === null) {
      map.fitBounds(bounds);
    }

    // Display the legend
    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = function (map) {
      const div = L.DomUtil.create('div', 'info legend');
      for (const polygonId in mapData.polygons) {
        const polygon = mapData.polygons[polygonId];

        // Add a colored square with the polygon's color
        // The "box-shadow" style is used to prevent a print css issue:
        // browsers often don't render colored background upon printing
        div.innerHTML += '<span><i style="box-shadow: inset 0 0 0 50px ' + polygon.color + '; background: ' + polygon.color + '"></i> ' + polygon.label + '</span>';
      }
      return div;
    };
    legend.addTo(map);

    // Bypass an issue with leaflet detecting a bad icon url, caused by
    // assets versioning
    L.Icon.Default.prototype.options.imagePath = '/static/leaflet/images/';

    // Upon page printing, the map container width is reduced, so we need to
    // make sure the map displays correctly with the new size.
    window.matchMedia('print').addEventListener("change", function (query) {
      if (query.matches) {
        map.invalidateSize();
      }
    });

    // Track some events to Matomo
    map.on('baselayerchange', function (e) {
      let mapType = mapData["type"];  // criterion or regulation
      let action;
      if (mapType === "criterion") {
        action = "MilieuMapSwitchLayer";
      } else {
        action = "PerimeterMapSwitchLayer";
      }
      _paq.push(['trackEvent', 'Content', action, e.name]);
      console.log('Layer changed to ' + action + " " + e.name);
    });

    return map;
  };

})(this, L, window._paq || []);

window.addEventListener('load', function () {
  var MAPS = window.MAPS || {};
  var configurator = new MapConfigurator(MAPS);
  configurator.init();
});
