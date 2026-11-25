class FullScreenControl extends L.Control {
  ANCHOR_CLASS_NAME = "fs-map-was-here";
  DIALOG_CLASS_NAME = "full-screen-map";
  FS_CONTENT_CLASS_NAME = "full-screen-map-content";
  BUTTON_CLASS_NAME = "leaflet-controls-full-screen-toggle";
  toggleFullScreen = function (map) {
    const container = map.getContainer().closest("." + this.FS_CONTENT_CLASS_NAME);
    const is_currently_fullscreen = container.closest("dialog");
    if (is_currently_fullscreen) {
      this.closeFullScreenModal(container, map);
    } else {
      this.openFullScreenModal(container, map);
    }
  }

  closeFullScreenModal(container, map) {
    const where_should_i_put_my_map_back = document.querySelector("." + this.ANCHOR_CLASS_NAME);
    where_should_i_put_my_map_back.classList.remove(this.ANCHOR_CLASS_NAME);
    where_should_i_put_my_map_back.appendChild(container);
    document.querySelector("dialog." + this.DIALOG_CLASS_NAME).remove();
    this.changeButtonText(container, "Agrandir la carte");
    setTimeout(() => {
      map.invalidateSize()
    }, 150);
  }

  openFullScreenModal(container, map) {
    container.parentElement.classList.add(this.ANCHOR_CLASS_NAME);
    const modal = L.DomUtil.create("dialog", this.DIALOG_CLASS_NAME);
    document.querySelector("body").append(modal);
    modal.appendChild(container);

    modal.addEventListener("close", () => {
      this.closeFullScreenModal(container, map);
    });
    this.changeButtonText(container, "Réduire la carte");
    modal.showModal();
    setTimeout(() => {
      map.invalidateSize()
    }, 150);
  }

  changeButtonText(container, text_content) {
    const control_button = container.querySelector("." + this.BUTTON_CLASS_NAME);
    control_button.querySelector("span.fr-sr-only").innerText = text_content
    control_button.title = text_content
  }

  onAdd(map) {
    if (!map.getContainer().closest("." + this.FS_CONTENT_CLASS_NAME)) {
      return L.DomUtil.create("span"); // nothing to do if full screen is not enabled for this map
    }
    const control_button = L.DomUtil.create("button", this.BUTTON_CLASS_NAME);
    control_button.type = "button";
    control_button.title = "Agrandir la carte";
    const text_content = L.DomUtil.create("span", "fr-sr-only", control_button);
    text_content.innerText = "Agrandir la carte";

    L.DomEvent.on(control_button, "click", (e) => {
      this.toggleFullScreen(map, control_button);
    });

    return control_button;
  }

  onRemove(map) {
    // Nothing to do here
  }
}

L.Control.FullScreen = FullScreenControl
L.control.fullscreen = function (options) {
  return new L.Control.FullScreen(options)
};
