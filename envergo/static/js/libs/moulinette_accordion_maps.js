(function(exports, L) {
  'use strict';

  /**
   * Initialize the leaflet maps for the criteria accordions.
   */
  const MapConfigurator = function(maps) {
    this.maps = maps;
  };
  exports.MapConfigurator = MapConfigurator;

  MapConfigurator.prototype.init = function() {
    for (const map in this.maps) {
      this.initMap(map);
    };
  };

  MapConfigurator.prototype.initMap = function(mapId) {
    const mapData = this.maps[mapId];
    const center = mapData.center;

    // Damn this constant lat and lng order mixing
    const centerCoords = [center.coordinates[1], center.coordinates[0]];
    const map = L.map(mapId, { maxZoom: 21 }).setView(centerCoords, 17);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 22,
      maxNativeZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
    }).addTo(map);

    // Display the project's coordinates as a maker
    const marker = L.marker(centerCoords);
    marker.addTo(map);

    // Display all polygons
    for (const polygonId in mapData.polygons) {
      const polygon = mapData.polygons[polygonId];
      const polygonJson = L.geoJSON(
        polygon['polygon'], { style: { color: polygon['color'], fillColor: polygon['color'] } });
      polygonJson.addTo(map);
    }

    // Display the legend
    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = function(map) {
      const div = L.DomUtil.create('div', 'info legend');
      for (const polygonId in mapData.polygons) {
        const polygon = mapData.polygons[polygonId];

        div.innerHTML += '<span><i style="background: ' + polygon.color + '"></i> ' + polygon.label + '</span>';
      }
      return div;
    };
    legend.addTo(map);

    // Bypass an issue with leaflet detecting a bad icon url, caused by
    // assets versioning
    L.Icon.Default.prototype.options.imagePath = '/static/leaflet/images/';
    return map;
  };

})(this, L);

window.addEventListener('load', function() {
  var CRITERIA_MAPS = window.CRITERIA_MAPS || {};
  var configurator = new MapConfigurator(CRITERIA_MAPS);
  configurator.init();
});
