/**
 * Create a basic drag'n'drop support for file inputs
 */
(function(exports) {
  'use strict';

  /**
   * Make the input[type=file] container a Drag'n'Drop zone
   *
   * Droping a file into the box does not uploads the file but sets
   * the input value.
   */
  const DragNDrop = function(box) {
    this.box = box;

    const input = box.querySelector('input[type=file]');
    this.input = input;

    this.registerEvents();
  };
  exports.DragNDrop = DragNDrop;

  DragNDrop.prototype.registerEvents = function() {

    this.box.addEventListener('dragover', function(evt) {
      evt.preventDefault();
    }.bind(this));

    this.box.addEventListener('dragenter', function(evt) {
      evt.preventDefault();
      this.box.classList.add('draghover');
    }.bind(this));

    this.box.addEventListener('dragleave', function(evt) {
      evt.preventDefault();
      this.box.classList.remove('draghover');
    }.bind(this));

    this.box.addEventListener('dragend', function(evt) {
      evt.preventDefault();
      this.box.classList.remove('draghover');
    }.bind(this));

    this.box.addEventListener('drop', function(evt) {
      evt.preventDefault();
      this.box.classList.remove('draghover');
      this.input.files = evt.dataTransfer.files;
    }.bind(this));
  };

})(this);


window.addEventListener('load', function() {
  // Activate a drag'n'drop helper for all input[type=file] fields
  // This selector class is set in the `_input_file_snippet.html` template
  const boxes = document.querySelectorAll(".input-file-box");
  boxes.forEach(function(box) {
    new DragNDrop(box);
  });
});
