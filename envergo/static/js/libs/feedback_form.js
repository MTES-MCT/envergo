const api = window['dsfr'];

const DialogSelector = {
  DIALOG: api.internals.ns.selector('dialog'),
  BODY: api.internals.ns.selector('dialog__body')
};

class DialogButton extends api.core.DisclosureButton {
  constructor() {
    super(api.core.DisclosureType.OPENED);
  }

  static get instanceClassName() {
    return 'DialogButton';
  }
}

class Dialog extends api.core.Disclosure {
  constructor() {
    super(api.core.DisclosureType.OPENED, DialogSelector.DIALOG, DialogButton, 'DialogsGroup');
    this.scrolling = this.resize.bind(this, false);
    this.resizing = this.resize.bind(this, true);
  }

  static get instanceClassName() {
    return 'Dialog';
  }

  init() {
    super.init();
    this.listen('click', this.click.bind(this));
    this.listenKey(api.core.KeyCodes.ESCAPE, this.conceal.bind(this, false, false), true, true);
  }

  get body() {
    return this.element.getDescendantInstances('DialogBody', 'Dialog')[0];
  }

  click(e) {
    if (e.target === this.node) this.conceal();
  }

  disclose(withhold) {
    if (!super.disclose(withhold)) return false;
    // if (this.body) this.body.activate();
    this.setAttribute('aria-dialog', 'true');
    this.setAttribute('open', 'true');
    return true;
  }

  conceal(withhold, preventFocus) {
    if (!super.conceal(withhold, preventFocus)) return false;
    this.isScrollLocked = false;
    this.removeAttribute('aria-dialog');
    this.removeAttribute('open');
    // if (this.body) this.body.deactivate();
    return true;
  }
}

api.dialog = {
  Dialog: Dialog,
  DialogButton: DialogButton,
  DialogSelector: DialogSelector
};

api.internals.register(api.dialog.DialogSelector.DIALOG, api.dialog.Dialog);
