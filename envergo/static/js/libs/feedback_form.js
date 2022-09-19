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
  }

  static get instanceClassName() {
    return 'Dialog';
  }

  init() {
    super.init();
    this.listen('click', this.click.bind(this));
    this.listenKey(api.core.KeyCodes.ESCAPE, this.conceal.bind(this, false, false), true, true);
  }

  disclose(withhold) {
    if (!super.disclose(withhold)) return false;
    this.setAttribute('aria-dialog', 'true');
    this.setAttribute('open', 'true');
    return true;
  }

  conceal(withhold, preventFocus) {
    if (!super.conceal(withhold, preventFocus)) return false;
    this.removeAttribute('aria-dialog');
    this.removeAttribute('open');
    return true;
  }
}

api.dialog = {
  Dialog: Dialog,
  DialogButton: DialogButton,
  DialogSelector: DialogSelector
};

api.internals.register(api.dialog.DialogSelector.DIALOG, api.dialog.Dialog);
