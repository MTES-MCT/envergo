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
    const options = this.maps[mapId];
    const mapData = options.map;
    const centerJson = mapData.center;
    const center = [centerJson.coordinates[1], centerJson.coordinates[0]];
    const map = L.map(options['divId'], { maxZoom: 21 }).setView(center, 17);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 22,
      maxNativeZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
    }).addTo(map);

    // Bypass an issue with leaflet detecting a bad icon url, caused by
    // assets versioning
    L.Icon.Default.prototype.options.imagePath = '/static/leaflet/images/';
    const marker = L.marker(center);
    marker.addTo(map);
    return map;
  };

})(this, L);

window.addEventListener('load', function() {
  var configurator = new MapConfigurator(CRITERIA_MAPS);
  configurator.init();
});
