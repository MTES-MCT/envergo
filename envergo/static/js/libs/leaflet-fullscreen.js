class FullScreenControl extends L.Control {
  /*
  To yield full screen, adds a class .full-screen on map container.
  Deals with button text (in French) and a basic focus trap.
  If you need some element to stay focusable with keyboard while full screen is activated,
  add class focusable-during-map-full-screen on itself or any of its ancestors.
   */
  toggleFullScreen = function(map, fs_button, forced_toggle_value) {
    const resulting_fullscreen_state = map.getContainer().classList.toggle("full-screen", forced_toggle_value);
    setTimeout(() => {map.invalidateSize()}, 70);
    const text_content = resulting_fullscreen_state ? "Réduire la carte" : "Agrandir la carte";
    fs_button.querySelector("span.fr-sr-only").innerText = text_content
    fs_button.title = text_content
  }

  onAdd(map) {
    const fs_button = L.DomUtil.create("button", "leaflet-controls-full-screen-toggle")
    fs_button.type = "button"
    fs_button.title = "Agrandir la carte"
    const text_content = L.DomUtil.create("span", "fr-sr-only", fs_button)
    text_content.innerText = "Agrandir la carte"

    L.DomEvent.on(fs_button, "click", (e) => {
      this.toggleFullScreen(map, fs_button);
    });

    L.DomEvent.on(map.getContainer(), "keyup", (e) => {
      if (e.key === "Escape") {
        this.toggleFullScreen(map, fs_button, false);
      }
    });

    // basic focus trap for modal behaviour
    L.DomEvent.on(window, "focusout", (e) => {
      const container = map.getContainer();
      if (!container.classList.contains("full-screen")) {
        // full screen disabled: no need for focus trap
        return;
      }
      if (!e.relatedTarget) {
        // user has clicked somewhere outside the window
        return;
      }
      if (!container.contains(e.relatedTarget) && !e.relatedTarget.closest(".focusable-during-map-full-screen")) {
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
