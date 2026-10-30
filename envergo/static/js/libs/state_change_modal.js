/**
 * Drives the dynamic behaviour of the "edit dossier state" modal.
 *
 * Three concerns react to the stage and decision <select>s:
 *  - the per-stage objective help text,
 *  - the closing fields (simulation check, prefectural order, applicant
 *    message) plus the message template pre-filled from the decision,
 *  - the switch of an RU dossier to authorisation. It pre-fills, relabels and
 *    groups the due date and the applicant message.
 *
 * This is purely an instructor convenience: StateChangeForm re-enforces every
 * rule server-side, so nothing here is load-bearing for data integrity.
 */
(function (exports) {
  'use strict';

  const STAGE_CLOSED = "closed";
  const STAGE_AUTHORIZATION = "instruction_a";

  const DECISION = {
    UNSET: "unset",
    DROPPED: "dropped",
    TACIT: "tacit_agreement",
    EXPRESS: "express_agreement",
    OPPOSITION: "opposition",
  };

  // Closing fields and the decisions that make them mandatory. A field is
  // shown if it is mandatory; `companions` are sibling elements (e.g. an
  // info notice) that follow the same visibility. Mirrors
  // StateChangeForm.clean_closing_fields.
  const CLOSING_FIELDS = [
    {
      groupId: "form-group-simulation_check",
      isMandatory: (d) => d !== DECISION.UNSET && d !== DECISION.DROPPED,
    },
    {
      groupId: "form-group-prefectural_order",
      isMandatory: (d) => d === DECISION.EXPRESS || d === DECISION.OPPOSITION,
      companions: ["prefectural-order-supersede-notice"],
    },
  ];

  // Date and comment fields hidden while closing: a closing is always
  // effective immediately, with no next due date nor back-dating.
  const NON_CLOSING_FIELD_IDS = [
    "form-group-due_date",
    "form-group-update_comment",
    "form-group-status_date",
  ];

  const closingMessageTemplateId = (decision) => `closing-message--${decision}`;
  const SWITCH_MESSAGE_TEMPLATE_ID = "authorization-switch-message";

  // Fields whose label reads differently during a switch to authorisation.
  const SWITCH_LABELED_FIELDS = ["due_date", "applicant_message"];

  const show = (elt, visible) => {
    if (elt) elt.style.display = visible ? "block" : "none";
  };

  class StateChangeModal {
    constructor(form) {
      // Inputs that drive the modal, and the fields whose state they control.
      this.stageInput = form.querySelector("#id_stage");
      this.decisionInput = form.querySelector("#id_decision");
      this.dueDateInput = form.querySelector("#id_due_date");
      this.applicantMessageInput = form.querySelector("#id_applicant_message");
      this.dueDateGroup = document.getElementById("form-group-due_date");
      this.decisionGroup = document.getElementById("form-group-decision");
      this.applicantMessageGroup = document.getElementById("form-group-applicant_message");
      this.submitButton = form.querySelector("button[type='submit']");

      // Undefined when the dossier cannot switch to authorisation.
      this.switchDueDate = form.dataset.authorizationSwitchDueDate;

      // Each label keeps its server-rendered content, restored after a switch.
      this.switchLabels = SWITCH_LABELED_FIELDS.map((name) => {
        const label = document.querySelector(`#form-group-${name} > label`);
        return {
          label,
          serverContent: label.innerHTML,
          switchContent: document.getElementById(`authorization-switch-label--${name}`)?.innerHTML.trim(),
        };
      });

      // Template that last filled the applicant message (see fillApplicantMessage).
      this.filledTemplateId = null;
      // Instructor's text for each template id, restored when its template comes back.
      this.drafts = new Map();
    }

    /** Wire the inputs and render the initial state. */
    init() {
      this.relocateSupersedeNotice();

      this.stageInput.addEventListener("change", () => {
        this.prefillSwitchDueDate();
        this.refresh();
      });
      this.decisionInput.addEventListener("change", () => this.refresh());

      // Keep a message the server rendered, e.g. after a validation error.
      this.filledTemplateId = this.messageTemplateId;
      this.refresh();
    }

    get stage() {
      return this.stageInput.value;
    }
    get decision() {
      return this.decisionInput.value;
    }
    get isClosing() {
      return this.stage === STAGE_CLOSED;
    }
    get canSwitchToAuthorization() {
      return this.switchDueDate !== undefined;
    }
    get isAuthorizationSwitch() {
      return this.canSwitchToAuthorization && this.stage === STAGE_AUTHORIZATION;
    }

    /** Id of the template the applicant message starts from, or null when hidden. */
    get messageTemplateId() {
      let templateId = null;
      if (this.isClosing && this.decision !== DECISION.UNSET) {
        templateId = closingMessageTemplateId(this.decision);
      } else if (this.isAuthorizationSwitch) {
        templateId = SWITCH_MESSAGE_TEMPLATE_ID;
      }
      return templateId;
    }

    /** Re-render everything that depends on the stage / decision selection. */
    refresh() {
      this.syncStageObjective();
      this.syncClosingFields();
      this.syncApplicantMessage();
      this.syncSwitchLabels();
      this.syncFieldOrder();
    }

    /**
     * Reveal the objective help text for the selected stage.
     *
     * Every stage's objective block is rendered server-side and hidden; only
     * the one matching the current stage is shown.
     */
    syncStageObjective() {
      document.querySelectorAll(".stage-objective").forEach((elt) => show(elt, false));
      show(document.getElementById(`stage-objective--${this.stage}`), true);
    }

    /**
     * Toggle the fields specific to closing a dossier.
     *
     * Closing hides the date/comment fields and reveals the simulation check
     * and prefectural order per the decision. Visibility tracks the
     * server-side requirements, so the instructor only sees the fields the
     * form will actually demand.
     */
    syncClosingFields() {
      NON_CLOSING_FIELD_IDS.forEach((id) => show(document.getElementById(id), !this.isClosing));
      if (this.isClosing) this.dueDateInput.value = "";

      CLOSING_FIELDS.forEach(({ groupId, isMandatory, companions = [] }) => {
        const visible = this.isClosing && isMandatory(this.decision);
        show(document.getElementById(groupId), visible);
        companions.forEach((id) => show(document.getElementById(id), visible));
      });
    }

    /** Show the applicant message, filled from the template of the current mode. */
    syncApplicantMessage() {
      const templateId = this.messageTemplateId;
      show(this.applicantMessageGroup, templateId !== null);
      this.fillApplicantMessage(templateId);
    }

    /** Show the switch labels during a switch, the server-rendered ones otherwise. */
    syncSwitchLabels() {
      this.switchLabels.forEach(({ label, serverContent, switchContent }) => {
        label.innerHTML = this.isAuthorizationSwitch ? switchContent : serverContent;
      });
    }

    /**
     * During a switch, put the due date and the message stating it right
     * under the decision. Otherwise, restore the server order.
     */
    syncFieldOrder() {
      if (this.isAuthorizationSwitch) {
        this.decisionGroup.after(this.dueDateGroup, this.applicantMessageGroup);
      } else {
        this.decisionGroup.before(this.dueDateGroup);
        this.submitButton.before(this.applicantMessageGroup);
      }
    }

    /**
     * Fill the applicant message for the given template.
     *
     * Each template keeps the instructor's draft. Moving to another template
     * saves the current text and restores that template's draft. A blank
     * draft gives way to the template text.
     */
    fillApplicantMessage(templateId) {
      if (templateId === null) return;

      const template = document.getElementById(templateId);
      if (!template) return;

      const isSameTemplate = templateId === this.filledTemplateId;
      const hasMessage = this.applicantMessageInput.value.trim() !== "";
      if (isSameTemplate && hasMessage) return;

      if (this.filledTemplateId !== null) {
        this.drafts.set(this.filledTemplateId, this.applicantMessageInput.value);
      }

      const draft = this.drafts.get(templateId) ?? "";
      const hasDraft = draft.trim() !== "";
      this.applicantMessageInput.value = hasDraft ? draft : template.textContent.trim();
      this.filledTemplateId = templateId;
    }

    /** On a switch, pre-fill an empty due date with the default deadline. */
    prefillSwitchDueDate() {
      if (!this.isAuthorizationSwitch) return;
      if (this.dueDateInput.value !== "") return;

      this.dueDateInput.value = this.switchDueDate;
    }

    /**
     * Move the supersede notice under the file input.
     *
     * The notice is rendered after the form because the fields render through
     * a shared snippet that cannot interleave arbitrary markup.
     */
    relocateSupersedeNotice() {
      const notice = document.getElementById("prefectural-order-supersede-notice");
      const orderField = document.getElementById("form-group-prefectural_order");
      if (notice && orderField) {
        orderField.insertAdjacentElement("afterend", notice);
      }
    }

  }

  exports.StateChangeModal = StateChangeModal;
})(this);

window.addEventListener("load", function () {
  const form = document.querySelector("#state-change-modal form");
  if (form) {
    new StateChangeModal(form).init();
  }
});
