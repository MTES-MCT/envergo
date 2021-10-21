/**
 * Create a basic drag'n'drop support for file inputs
 */
(function(exports) {
  'use strict';

  const DragNDrop = function(box) {
    const input = box.querySelector('input[type=file]');
    this.box = box;
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
      console.log('dragleav');

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
  const boxes = document.querySelectorAll(".input-file-box");
  boxes.forEach(function(box) {
    new DragNDrop(box);
  });
});
