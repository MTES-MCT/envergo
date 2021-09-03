(function (exports, L, rewind) {
    'use strict';

    var ParcelMapApp = function () {};
    exports.ParcelMapApp = ParcelMapApp;

    ParcelMapApp.prototype.mapInit = function (map, options) {
        var layer = L.tileLayer(
            "https://wxs.ign.fr/parcellaire/geoportail/wmts?" +
            "&REQUEST=GetTile" +
            "&SERVICE=WMTS" +
            "&VERSION=1.0.0" +
            "&STYLE=PCI vecteur" +
            "&TILEMATRIXSET=PM" +
            "&FORMAT=image/png" +
            "&LAYER=CADASTRALPARCELS.PARCELLAIRE_EXPRESS" +
            "&TILEMATRIX={z}" +
            "&TILEROW={y}" +
            "&TILECOL={x}", {
                minZoom: 0,
                maxZoom: 18,
                attribution: "IGN-F/Geoportail",
                tileSize: 256 // les tuiles du Géooportail font 256x256px
            }
        );
        layer.addTo(map);
        geojsonLayer = L.geoJSON().addTo(map);
        map.on('click', this.onMapClicked.bind(this));
    };

    ParcelMapApp.prototype.onMapClicked = function (e) {
        console.log("Map clicked " + e.latlng);

        var searchUrl =
            `https://geocodage.ign.fr/look4/parcel/reverse?searchGeom={"type":"Point","coordinates":[${e.latlng.lng},${e.latlng.lat}]}&returnTrueGeometry=true`;
        fetch(searchUrl)
            .then(response => {
                return response.json();
            })
            .then(response => {
                console.log(response);
                var parcel = response.features[0];
                var polygon = rewind(parcel.properties.trueGeometry);
                geojsonLayer.addData(polygon);
            });
    };






})(this, L, rewind);

const parcelMapApp = new ParcelMapApp();
