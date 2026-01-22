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

    // Damn this constant lat and lng order mixing
    const centerCoords = [center.coordinates[1], center.coordinates[0]];
    let settings = {
      maxZoom: 21,
      layers: [planLayer],
    };
    if (typeof mapData["fixed"] === 'object') {
      settings = { ...settings, ...mapData["fixed"] }
    }
    else {
      settings["zoomControl"] = !mapData["fixed"];
      settings["dragging"] = !mapData["fixed"];
      settings["doubleClickZoom"] = !mapData["fixed"];
      settings["scrollWheelZoom"] = !mapData["fixed"];
      settings["touchZoom"] = !mapData["fixed"];
      settings["keyboard"] = !mapData["fixed"];
    }
    const map = L.map(mapId, settings).setView(centerCoords, mapData['zoom']);

    // Display layer switching control
    const baseMaps = {
      "Plan": planLayer,
      "Satellite": satelliteLayer
    };

    const overlayMaps = {
      "Cadastre": pciLayer
    };

    const layerControl = L.control.layers(baseMaps, overlayMaps);
    layerControl.addTo(map);

    // Display the project's coordinates as a maker
    if(!("displayMarkerAtCenter" in mapData ) || mapData["displayMarkerAtCenter"]) { // default to true
      const marker = L.marker(centerCoords);
      marker.addTo(map);
    }
   // Display all polygons
    const bounds = L.latLngBounds();
    for (const polygonId in mapData.polygons) {
      const polygon = mapData.polygons[polygonId];
      const polygonJson = L.geoJSON(
        polygon['polygon'], { style: { color: polygon['color'], fillColor: polygon['color'], className: polygon['className'] } });
      bounds.extend(polygonJson.getBounds());
      polygonJson.addTo(map);
    }

    if(mapData["zoomOnGeometry"]){
      const geometry = mapData["zoomOnGeometry"];
      const geometryJson = L.geoJSON(geometry);
      const geometryBounds = geometryJson.getBounds();
      map.fitBounds(geometryBounds, { padding: [0.1, 0.1], maxZoom: 18 });
    } else if (mapData["zoom"] === null) {
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

    // Upon page printing, the map container width is reduced, so we need to
    // make sure the map displays correctly with the new size.
    const mql = window.matchMedia('print');
    if (mql.addEventListener) {
      mql.addEventListener("change", function (query) {
        if (query.matches) {
          map.invalidateSize();
        }
      });
    }

    // Subsequently, when the print page is closed, we must reset the maps to
    // it's original size
    window.addEventListener("afterprint", function () {
      map.invalidateSize();

      // Note: in firefox, the "afterprint" event is fired as soon as the
      // print preview window opens (go figure). So we have to use this hack
      // See https://bugzilla.mozilla.org/show_bug.cgi?id=1663290#c12
      window.addEventListener("focus", function () {
        map.invalidateSize();
      });
    });

    // Track some events to Matomo
    map.on('baselayerchange', function (e) {
      let action = this.getEventAction(mapData["type"]);
      _paq.push(['trackEvent', 'Content', action, e.name]);
    }.bind(this));

    // Enable cadastre overlay
    map.on('overlayadd', function (e) {
      let action = this.getEventAction(mapData["type"]);
      _paq.push(['trackEvent', 'Content', action, "CadastreOn"]);
    }.bind(this));

    // Disable cadastre overlay
    map.on('overlayremove', function (e) {
      let action = this.getEventAction(mapData["type"]);
      _paq.push(['trackEvent', 'Content', action, "CadastreOff"]);
    }.bind(this));

    const event = new CustomEvent('mapInitialized', { detail: {id: mapId, map: map, data: mapData}});
    window.dispatchEvent(event);

    return map;
  };

  // Return the expected "action" field for matomo event
  MapConfigurator.prototype.getEventAction = function (mapType) {
    let action;
    switch (mapType) {
      case "criterion":
        action = "MilieuMapSwitchLayer";
        break;
      case "regulation":
        action = "PerimeterMapSwitchLayer";
        break;
      case "location":
        action = "LocationMapSwitchLayer";
        break;
      default:
        action = "UnknownMapType";
    }
    return action;
  };

})(this, L, window._paq);

window.addEventListener('load', function () {
  var MAPS = window.MAPS || {};
  var configurator = new MapConfigurator(MAPS);
  configurator.init();
});
