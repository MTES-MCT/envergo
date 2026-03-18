if (!window.$crisp) {
  console.error("Crisp is not loaded");
} else if (!CRISP_EVALUATION_SCENARIO_ID) {
  console.error("Crisp evaluation scenario ID is not set");
} else {
  // Injecter la ref de l'avis
  window.$crisp.push(["set", "session:data", ["ref_avis", EVALUATION_REFERENCE]]);
  // Déclencher le scénario à chaque ouverture du chatbox
  window.$crisp.push(["on", "chat:opened", function() {
    window.$crisp.push(["do", "bot:scenario:run", [CRISP_EVALUATION_SCENARIO_ID]]);
  }]);
}
