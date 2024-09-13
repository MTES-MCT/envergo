[1mdiff --git a/envergo/haies/static/saisie/app.js b/envergo/haies/static/saisie/app.js[m
[1mindex 8f98e579..a4f653d6 100644[m
[1m--- a/envergo/haies/static/saisie/app.js[m
[1m+++ b/envergo/haies/static/saisie/app.js[m
[36m@@ -11,8 +11,8 @@[m [mcreateApp({[m
     let map = null;[m
     let nextId = ref(0);[m
 [m
[31m-    const normalStyle = { c[7molor: 'red', weight: 5, opacity: 0.75[27m };[m
[31m-    const hoveredStyle = {[7m color: 'red', weight: 7, opacity: 0.95 [27m};[m
[32m+[m[32m    const normalStyle = { c[7mlassName: 'hedge'[27m };[m
[32m+[m[32m    const hoveredStyle = {[7m[27m};[m
     const fitBoundsOptions = { padding: [25, 25] };[m
 [m
     const calculatePolylineLength = (latLngs) => {[m
[36m@@ -71,11 +71,13 @@[m [mcreateApp({[m
       // Gérer l'état de survol pour la polyline[m
       currentPolyline.on('mouseover', () => {[m
         currentPolyline.setStyle(hoveredStyle);[m
[32m+[m[32m        currentPolyline._path.classList.add("hovered");[m
         polylineData.isHovered = true;[m
       });[m
 [m
       currentPolyline.on('mouseout', () => {[m
         currentPolyline.setStyle(normalStyle);[m
[32m+[m[32m        currentPolyline._path.classList.remove("hovered");[m
         polylineData.isHovered = false;[m
 [m
       });[m
[36m@@ -94,10 +96,17 @@[m [mcreateApp({[m
 [m
     const handleMouseOver = (polyline) => {[m
       polyline.polylineLayer.setStyle(hoveredStyle);[m
[32m+[m[32m      if (Object.hasOwn(polyline.polylineLayer, "_path")) {[m
[32m+[m[32m        polyline.polylineLayer._path.classList.add("hovered");[m
[32m+[m[32m      }[m
[32m+[m
     };[m
 [m
     const handleMouseOut = (polyline) => {[m
       polyline.polylineLayer.setStyle(normalStyle);[m
[32m+[m[32m      if (Object.hasOwn(polyline.polylineLayer, "_path")) {[m
[32m+[m[32m        polyline.polylineLayer._path.classList.remove("hovered");[m
[32m+[m[32m      }[m
     };[m
 [m
     // Centrer la carte sur la polyline lorsque l'utilisateur clique sur l'entrée dans la liste[m
[1mdiff --git a/envergo/static/sass/project_haie.scss b/envergo/static/sass/project_haie.scss[m
[1mindex f2056165..be8080d1 100644[m
[1m--- a/envergo/static/sass/project_haie.scss[m
[1m+++ b/envergo/static/sass/project_haie.scss[m
[36m@@ -40,6 +40,17 @@[m [mdiv#app {[m
     #map {[m
       flex: 1;[m
       height: 100%;[m
[32m+[m
[32m+[m[32m      .hedge {[m
[32m+[m[32m        stroke: #ca0020;[m
[32m+[m[32m        stroke-width: 5;[m
[32m+[m
[32m+[m[32m        &:hover,[m
[32m+[m[32m        &.hovered {[m
[32m+[m[32m          stroke: #ca0020;[m
[32m+[m[32m          stroke-width: 7;[m
[32m+[m[32m        }[m
[32m+[m[32m      }[m
     }[m
 [m
     #sidebar {[m
[36m@@ -83,6 +94,10 @@[m [mdiv#app {[m
               visibility: visible;[m
             }[m
           }[m
[32m+[m
[32m+[m[32m          &:active {[m
[32m+[m[32m            background-color: #ca002040;[m
[32m+[m[32m          }[m
         }[m
       }[m
     }[m
