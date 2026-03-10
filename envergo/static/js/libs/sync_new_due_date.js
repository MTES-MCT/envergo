/**
 * Helper for the "resume instruction" feature.
 *
 * When the use sets the "info received at" field, automatically update
 * the "new due date" field.
 */
(function (exports) {
  const DueDateInput = function (due_date_input, receipt_date_input) {
    this.due_date_input = due_date_input;
    this.receipt_date_input = receipt_date_input;

    // the `Date` constructor parses dates formatted in iso 8601 format
    this.suspension_date = new Date(due_date_input.dataset.suspensionDate);
    this.original_due_date = new Date(due_date_input.dataset.originalDueDate);

    receipt_date_input.addEventListener("change", this.on_receipt_date_changed.bind(this));
    this.on_receipt_date_changed();
  };
  exports.DueDateInput = DueDateInput;

  DueDateInput.prototype.on_receipt_date_changed = function () {
    // The Date js api is absolutely insane and does not make any sense

    // Since the input type is "date", `value` is a string but in iso 8601 format
    let receipt_date = new Date(this.receipt_date_input.value);

    // Substracting two dates returns a value in milliseconds :'(
    let date_diff = receipt_date - this.suspension_date;

    // We want to do this:
    // let new_due_date = this.original_due_date + date_diff;
    // But we can't
    // Adding a date and a value in milliseconds concatenates the string representations
    // So you get this:
    // "Sun Nov 29 2020 01:00:00 GMT+0100 (heure normale d’Europe centrale)345600000"

    // The `milliseconds` date property is the actual precise milliseconds value,
    // so a value between 0 and 999
    // BUT if you use `setMilliseconds` with a value outside this range, js will
    // update the Date object accordingly
    // See https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date/setUTCMilliseconds#description
    let new_due_date = new Date(this.original_due_date);
    new_due_date.setUTCMilliseconds(new_due_date.getUTCMilliseconds() + date_diff);

    // Of course, you cannot set a value for a `type=date` input with a Date object,
    // you have to use an iso 8601 date format
    this.due_date_input.value = new_due_date.toISOString().substring(0, 10);
  };

})(this);
