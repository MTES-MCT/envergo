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

  DragNDrop.prototype.updateFileState = function() {
    const successMsg = this.box.querySelector('.success-box-msg');
    if (this.input.files && this.input.files.length > 0) {
      this.box.classList.add('has-file');
      if (successMsg) {
        const file = this.input.files[0];
        const size = file.size < 1024 * 1024
          ? (file.size / 1024).toFixed(0) + ' Ko'
          : (file.size / (1024 * 1024)).toFixed(1) + ' Mo';
        successMsg.textContent = file.name + ' (' + size + ')';
      }
    } else {
      this.box.classList.remove('has-file');
      if (successMsg) {
        successMsg.textContent = '';
      }
    }
  };

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
      this.updateFileState();
    }.bind(this));

    this.input.addEventListener('change', function() {
      this.updateFileState();
    }.bind(this));

    const removeBtn = this.box.querySelector('.remove-file-btn');
    removeBtn.addEventListener('click', function() {
      this.input.value = '';
      this.updateFileState();
    }.bind(this));
  };

})(this);


window.addEventListener('load', function() {
  // Activate a drag'n'drop helper for all input[type=file] fields
  // This selector class is set in the `_input_file_snippet.html` template
  const boxes = document.querySelectorAll(".input-file-box");
  boxes.forEach(function(box) {
    if (!box.dataset.dragInit) {
      new DragNDrop(box);
      box.dataset.dragInit = "true";
    }
  });
});
