/**
 * Drives the dynamic behaviour of the "edit dossier state" modal.
 *
 * Three independent concerns react to the stage and decision <select>s:
 *  - the per-stage objective help text,
 *  - the Démarches Simplifiées state-change notice,
 *  - the closing fields (simulation check, prefectural order, applicant
 *    message) plus the message template pre-filled from the decision.
 *
 * This is purely an instructor convenience: ProcedureForm re-enforces every
 * rule server-side, so nothing here is load-bearing for data integrity.
 */
(function (exports) {
  'use strict';

  const STAGE_CLOSED = "closed";

  const DECISION = {
    UNSET: "unset",
    DROPPED: "dropped",
    TACIT: "tacit_agreement",
    EXPRESS: "express_agreement",
    OPPOSITION: "opposition",
  };

  // DS states whose transition is worth an extra word of warning.
  const DS_STATE = {
    UNDER_INSTRUCTION: "en_instruction",
    UNDER_CONSTRUCTION: "en_construction",
  };

  // Closing fields and the decisions that make them mandatory. A field is
  // shown if it is mandatory; `companions` are sibling elements (e.g. an
  // info notice) that follow the same visibility. Mirrors
  // ProcedureForm.clean_closing_fields.
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
    {
      groupId: "form-group-applicant_message",
      isMandatory: (d) => d !== DECISION.UNSET,
    },
  ];

  // Date and comment fields hidden while closing: a closing is always
  // effective immediately, with no next due date nor back-dating.
  const NON_CLOSING_FIELD_IDS = [
    "form-group-due_date",
    "form-group-update_comment",
    "form-group-status_date",
  ];

  const show = (elt, visible) => {
    if (elt) elt.style.display = visible ? "block" : "none";
  };
  const readJson = (id) => JSON.parse(document.getElementById(id).textContent);

  class StateChangeModal {
    constructor(form) {
      // Inputs that drive the modal, and the fields whose state they control.
      this.stageInput = form.querySelector("#id_stage");
      this.decisionInput = form.querySelector("#id_decision");
      this.dueDateInput = form.querySelector("#id_due_date");
      this.applicantMessageInput = form.querySelector("#id_applicant_message");

      // Démarches Simplifiées state-change notice.
      this.stateChangeNotice = document.getElementById("state-change-notice");
      this.stateChangeText = document.getElementById("state-change-transition-text");
      this.currentDsState = form.dataset.currentDsStatus;
      this.currentStage = readJson("current-stage");
      this.dsStateByStageDecision = readJson("ds-status-mapping");
      this.dsStateLabels = readJson("ds-status-labels");
      this.forbiddenTransitions = readJson("forbidden-transitions");
    }

    /**
     * Wire the selects and render the initial state.
     *
     * Both selects trigger a full re-render; they differ only in how they
     * treat the applicant message — picking a decision replaces it, changing
     * the stage keeps what is already there (see fillApplicantMessage).
     */
    init() {
      this.relocateSupersedeNotice();

      this.stageInput.addEventListener("change", () => {
        this.sync();
        this.fillApplicantMessage({ overwrite: false });
      });
      this.decisionInput.addEventListener("change", () => {
        this.sync();
        this.fillApplicantMessage({ overwrite: true });
      });

      this.sync();
      this.fillApplicantMessage({ overwrite: false });
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

    /** Re-render everything that depends on the stage / decision selection. */
    sync() {
      this.syncStageObjective();
      this.syncClosingFields();
      this.syncStateChangeNotice();
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
     * Closing hides the date/comment fields and reveals the simulation check,
     * prefectural order and applicant message per the decision. Visibility
     * tracks the server-side requirements, so the instructor only sees the
     * fields the form will actually demand.
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

    /**
     * Warn the instructor when saving will change the Démarches Simplifiées
     * state.
     *
     * Shown only for a real, allowed transition: the target state differs from
     * the current one and the stage move is not forbidden.
     */
    syncStateChangeNotice() {
      const nextDsState = (this.dsStateByStageDecision[this.stage] || {})[this.decision];
      const changes =
        nextDsState &&
        nextDsState !== this.currentDsState &&
        !this.isForbidden(this.currentStage, this.stage);

      show(this.stateChangeNotice, changes);
      if (!changes) return;

      this.stateChangeText.textContent =
        `Le dossier passe de l'état « ${this.dsLabel(this.currentDsState)} » ` +
        `à « ${this.dsLabel(nextDsState)} » sur Démarche Numérique.` +
        this.dsTransitionHint(nextDsState);
    }

    /**
     * Pre-fill the applicant message from the selected decision's template.
     *
     * `overwrite` is false when the instructor did not explicitly pick the
     * decision (entering the closing flow, or first render after a validation
     * error): a message already typed or submitted must be preserved.
     */
    fillApplicantMessage({ overwrite }) {
      if (!this.isClosing) return;
      if (!overwrite && this.applicantMessageInput.value.trim() !== "") return;

      const template = document.getElementById(`closing-message--${this.decision}`);
      if (template) this.applicantMessageInput.value = template.textContent.trim();
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

    isForbidden(from, to) {
      return this.forbiddenTransitions.some(([f, t]) => f === from && t === to);
    }

    dsLabel(state) {
      return this.dsStateLabels[state] || state;
    }

    /**
     * Spell out what a DS state change means for the applicant: passing to
     * instruction locks their editing, returning to construction unlocks it.
     * Empty for transitions with no such effect.
     */
    dsTransitionHint(nextDsState) {
      if (nextDsState === DS_STATE.UNDER_INSTRUCTION) {
        return " Il ne sera donc plus modifiable par le demandeur.";
      }
      if (nextDsState === DS_STATE.UNDER_CONSTRUCTION) {
        return " Il sera donc à nouveau modifiable par le demandeur.";
      }
      return "";
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
