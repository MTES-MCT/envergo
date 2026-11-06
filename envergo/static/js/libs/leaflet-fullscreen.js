class FullScreenControl extends L.Control {
  onAdd(map) {
    const fs_button = L.DomUtil.create("button", "leaflet-controls-full-screen-toggle")
    fs_button.type = "button"
    const text_content = L.DomUtil.create("span", "fr-sr-only", fs_button)
    text_content.innerText = "Plein écran"

    L.DomEvent.on(fs_button, "click", (e) => {
      map.getContainer().classList.toggle("full-screen");
      setTimeout(() => {map.invalidateSize()}, 70);
    });

    L.DomEvent.on(map.getContainer(), "keyup", (e) => {
      if (e.key === "Escape") {
        map.getContainer().classList.toggle("full-screen", false);
        setTimeout(() => {map.invalidateSize()}, 70);
      }
    });

    // basic focus trap for modal behaviour
    L.DomEvent.on(window, "focusout", (e) => {
      const container = map.getContainer();
      if (!container.classList.contains("full-screen")) {
        // full screen disabled: no need for focus trap
        return;
      }
      if (!container.contains(e.relatedTarget)) {
        // losing focus: force it back on first focusable element in container
        container.querySelector("a, button").focus({focusVisible:true})
      }
    })

    return fs_button
  }

  onRemove(map) {
    // Nothing to do here
  }
}

L.Control.FullScreen = FullScreenControl
L.control.fullscreen = function (options) {
	return new L.Control.FullScreen(options)
};
