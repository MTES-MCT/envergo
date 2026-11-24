[1mdiff --git i/envergo/petitions/models.py w/envergo/petitions/models.py[m
[1mindex fb8f5cda8..f24702101 100644[m
[1m--- i/envergo/petitions/models.py[m
[1m+++ w/envergo/petitions/models.py[m
[36m@@ -219,12 +219,10 @@[m [mclass InstructionMixin:[m
 [m
     def start_instruction(self, *, submission_date):[m
         """On dépôt, move the dossier into its instruction stage."""[m
[1;35m-        if self.is_regime_unique():[m
[31m-            instruction_stage = STAGES.instruction_d[m
[31m-            agreement_deadline = declaration_due_date(submission_date)[m
[1;35m-        else:[m
[31m-            instruction_stage = STAGES.instruction_h[m
[31m-            agreement_deadline = None[m
[32m+[m[32m        instruction_stage = self._first_instruction_stage()[m
[32m+[m[32m        agreement_deadline = self._agreement_deadline_on_entering([m
[32m+[m[32m            instruction_stage, submission_date[m
[1;36m+[m[1;36m        )[m
 [m
         log = StatusLog([m
             petition_project=self,[m
[36m@@ -378,16 +376,9 @@[m [mclass InstructionMixin:[m
     ):[m
         """An instructor sets the stage, decision and due date freely, outside the named actions.[m
 [m
[31m-        A régime unique dossier entering déclaration from another stage starts its[m
[31m-        agreement delay on `status_date`.[m
[32m+[m[32m        Entering a stage where silence means agreement starts the agreement delay on `status_date`.[m
         """[m
[31m-        enters_declaration = ([m
[31m-            stage == STAGES.instruction_d and self.stage != STAGES.instruction_d[m
[1;35m-        )[m
[31m-        if self.is_regime_unique() and enters_declaration:[m
[31m-            agreement_deadline = declaration_due_date(status_date)[m
[1;35m-        else:[m
[31m-            agreement_deadline = None[m
[32m+[m[32m        agreement_deadline = self._agreement_deadline_on_entering(stage, status_date)[m
 [m
         log = StatusLog([m
             petition_project=self,[m
[36m@@ -402,6 +393,28 @@[m [mclass InstructionMixin:[m
         )[m
         return self._record_event(log)[m
 [m
[32m+[m[32m    def _first_instruction_stage(self):[m
[32m+[m[32m        """The stage a dossier enters when its instruction starts."""[m
[1;36m+[m[1;36m        if self.is_regime_unique():[m
[32m+[m[32m            stage = STAGES.instruction_d[m
[1;36m+[m[1;36m        else:[m
[32m+[m[32m            stage = STAGES.instruction_h[m
[32m+[m[32m        return stage[m
[32m+[m
[32m+[m[32m    def _agreement_deadline_on_entering(self, stage, start_date: date) -> date | None:[m
[32m+[m[32m        """When silence turns into agreement, for a dossier entering `stage` on `start_date`.[m
[32m+[m
[32m+[m[32m        None when silence in `stage` means no agreement, or when the dossier is already there.[m
[32m+[m[32m        """[m
[32m+[m[32m        starts_agreement_delay = ([m
[32m+[m[32m            self.silence_rule_in(stage) == SilenceRule.AGREEMENT and self.stage != stage[m
[1;36m+[m[1;36m        )[m
[32m+[m
[32m+[m[32m        deadline = None[m
[32m+[m[32m        if starts_agreement_delay:[m
[32m+[m[32m            deadline = declaration_due_date(start_date)[m
[32m+[m[32m        return deadline[m
[32m+[m
     def _record_event(self, log):[m
         """Save the log of an instruction event, mirror it in « Démarche numérique », and return it."""[m
         with transaction.atomic():[m
[36m@@ -700,8 +713,19 @@[m [mclass PetitionProject(InstructionMixin, MoulinetteHaieUrlMixin, models.Model):[m
         decision_pending = self.stage in PENDING_DECISION_STAGES[m
 [m
         rule = None[m
[32m+[m[32m        # Testing the regime first skips the history query when no rule can apply.[m
         if self.is_regime_unique() and decision_pending:[m
[31m-            rule = SILENCE_RULE_BY_INSTRUCTION_STAGE.get(self.latest_instruction_stage)[m
[32m+[m[32m            rule = self.silence_rule_in(self.latest_instruction_stage)[m
[32m+[m[32m        return rule[m
[32m+[m
[32m+[m[32m    def silence_rule_in(self, stage) -> SilenceRule | None:[m
[32m+[m[32m        """What the administration's silence means for this dossier in `stage`.[m
[32m+[m
[32m+[m[32m        None outside the régime unique, or for a stage without a silence rule.[m
[32m+[m[32m        """[m
[32m+[m[32m        rule = None[m
[1;36m+[m[1;36m        if self.is_regime_unique():[m
[32m+[m[32m            rule = SILENCE_RULE_BY_INSTRUCTION_STAGE.get(stage)[m
         return rule[m
 [m
     @cached_property[m
[1mdiff --git i/envergo/petitions/tests/test_models.py w/envergo/petitions/tests/test_models.py[m
[1mindex 55666390c..eb5713af5 100644[m
[1m--- i/envergo/petitions/tests/test_models.py[m
[1m+++ w/envergo/petitions/tests/test_models.py[m
[36m@@ -205,6 +205,22 @@[m [mdef test_silence_rule_reads_the_history_only_when_a_rule_can_apply([m
         project.silence_rule[m
 [m
 [m
[32m+[m[32m@pytest.mark.parametrize([m
[32m+[m[32m    "category, stage, expected",[m
[32m+[m[32m    [[m
[32m+[m[32m        ("ru", STAGES.instruction_d, SilenceRule.AGREEMENT),[m
[32m+[m[32m        ("ru", STAGES.instruction_a, SilenceRule.REFUSAL),[m
[32m+[m[32m        ("ru", STAGES.closed, None),[m
[32m+[m[32m        ("hru", STAGES.instruction_d, None),[m
[32m+[m[32m    ],[m
[32m+[m[32m)[m
[32m+[m[32mdef test_silence_rule_in_a_stage(category, stage, expected):[m
[32m+[m[32m    """Only the régime unique's instruction stages carry a silence rule."""[m
[32m+[m[32m    project = PetitionProjectFactory.build(underscore_category=category)[m
[32m+[m
[32m+[m[32m    assert project.silence_rule_in(stage) == expected[m
[32m+[m
[32m+[m
 def test_form_url_adds_alternative_param():[m
     """form_url appends project_reference to the query string."""[m
     DCConfigHaieFactory()[m
[1mdiff --git i/envergo/petitions/models.py w/envergo/petitions/models.py[m
[1mindex fb8f5cda8..f24702101 100644[m
[1m--- i/envergo/petitions/models.py[m
[1m+++ w/envergo/petitions/models.py[m
[36m@@ -219,12 +219,10 @@[m [mclass InstructionMixin:[m
 [m
     def start_instruction(self, *, submission_date):[m
         """On dépôt, move the dossier into its instruction stage."""[m
[1;35m-        if self.is_regime_unique():[m
[31m-            instruction_stage = STAGES.instruction_d[m
[31m-            agreement_deadline = declaration_due_date(submission_date)[m
[1;35m-        else:[m
[31m-            instruction_stage = STAGES.instruction_h[m
[31m-            agreement_deadline = None[m
[32m+[m[32m        instruction_stage = self._first_instruction_stage()[m
[32m+[m[32m        agreement_deadline = self._agreement_deadline_on_entering([m
[32m+[m[32m            instruction_stage, submission_date[m
[1;36m+[m[1;36m        )[m
 [m
         log = StatusLog([m
             petition_project=self,[m
[36m@@ -378,16 +376,9 @@[m [mclass InstructionMixin:[m
     ):[m
         """An instructor sets the stage, decision and due date freely, outside the named actions.[m
 [m
[31m-        A régime unique dossier entering déclaration from another stage starts its[m
[31m-        agreement delay on `status_date`.[m
[32m+[m[32m        Entering a stage where silence means agreement starts the agreement delay on `status_date`.[m
         """[m
[31m-        enters_declaration = ([m
[31m-            stage == STAGES.instruction_d and self.stage != STAGES.instruction_d[m
[1;35m-        )[m
[31m-        if self.is_regime_unique() and enters_declaration:[m
[31m-            agreement_deadline = declaration_due_date(status_date)[m
[1;35m-        else:[m
[31m-            agreement_deadline = None[m
[32m+[m[32m        agreement_deadline = self._agreement_deadline_on_entering(stage, status_date)[m
 [m
         log = StatusLog([m
             petition_project=self,[m
[36m@@ -402,6 +393,28 @@[m [mclass InstructionMixin:[m
         )[m
         return self._record_event(log)[m
 [m
[32m+[m[32m    def _first_instruction_stage(self):[m
[32m+[m[32m        """The stage a dossier enters when its instruction starts."""[m
[1;36m+[m[1;36m        if self.is_regime_unique():[m
[32m+[m[32m            stage = STAGES.instruction_d[m
[1;36m+[m[1;36m        else:[m
[32m+[m[32m            stage = STAGES.instruction_h[m
[32m+[m[32m        return stage[m
[32m+[m
[32m+[m[32m    def _agreement_deadline_on_entering(self, stage, start_date: date) -> date | None:[m
[32m+[m[32m        """When silence turns into agreement, for a dossier entering `stage` on `start_date`.[m
[32m+[m
[32m+[m[32m        None when silence in `stage` means no agreement, or when the dossier is already there.[m
[32m+[m[32m        """[m
[32m+[m[32m        starts_agreement_delay = ([m
[32m+[m[32m            self.silence_rule_in(stage) == SilenceRule.AGREEMENT and self.stage != stage[m
[1;36m+[m[1;36m        )[m
[32m+[m
[32m+[m[32m        deadline = None[m
[32m+[m[32m        if starts_agreement_delay:[m
[32m+[m[32m            deadline = declaration_due_date(start_date)[m
[32m+[m[32m        return deadline[m
[32m+[m
     def _record_event(self, log):[m
         """Save the log of an instruction event, mirror it in « Démarche numérique », and return it."""[m
         with transaction.atomic():[m
[36m@@ -700,8 +713,19 @@[m [mclass PetitionProject(InstructionMixin, MoulinetteHaieUrlMixin, models.Model):[m
         decision_pending = self.stage in PENDING_DECISION_STAGES[m
 [m
         rule = None[m
[32m+[m[32m        # Testing the regime first skips the history query when no rule can apply.[m
         if self.is_regime_unique() and decision_pending:[m
[31m-            rule = SILENCE_RULE_BY_INSTRUCTION_STAGE.get(self.latest_instruction_stage)[m
[32m+[m[32m            rule = self.silence_rule_in(self.latest_instruction_stage)[m
[32m+[m[32m        return rule[m
[32m+[m
[32m+[m[32m    def silence_rule_in(self, stage) -> SilenceRule | None:[m
[32m+[m[32m        """What the administration's silence means for this dossier in `stage`.[m
[32m+[m
[32m+[m[32m        None outside the régime unique, or for a stage without a silence rule.[m
[32m+[m[32m        """[m
[32m+[m[32m        rule = None[m
[1;36m+[m[1;36m        if self.is_regime_unique():[m
[32m+[m[32m            rule = SILENCE_RULE_BY_INSTRUCTION_STAGE.get(stage)[m
         return rule[m
 [m
     @cached_property[m
[1mdiff --git i/envergo/petitions/tests/test_models.py w/envergo/petitions/tests/test_models.py[m
[1mindex 55666390c..eb5713af5 100644[m
[1m--- i/envergo/petitions/tests/test_models.py[m
[1m+++ w/envergo/petitions/tests/test_models.py[m
[36m@@ -205,6 +205,22 @@[m [mdef test_silence_rule_reads_the_history_only_when_a_rule_can_apply([m
         project.silence_rule[m
 [m
 [m
[32m+[m[32m@pytest.mark.parametrize([m
[32m+[m[32m    "category, stage, expected",[m
[32m+[m[32m    [[m
[32m+[m[32m        ("ru", STAGES.instruction_d, SilenceRule.AGREEMENT),[m
[32m+[m[32m        ("ru", STAGES.instruction_a, SilenceRule.REFUSAL),[m
[32m+[m[32m        ("ru", STAGES.closed, None),[m
[32m+[m[32m        ("hru", STAGES.instruction_d, None),[m
[32m+[m[32m    ],[m
[32m+[m[32m)[m
[32m+[m[32mdef test_silence_rule_in_a_stage(category, stage, expected):[m
[32m+[m[32m    """Only the régime unique's instruction stages carry a silence rule."""[m
[32m+[m[32m    project = PetitionProjectFactory.build(underscore_category=category)[m
[32m+[m
[32m+[m[32m    assert project.silence_rule_in(stage) == expected[m
[32m+[m
[32m+[m
 def test_form_url_adds_alternative_param():[m
     """form_url appends project_reference to the query string."""[m
     DCConfigHaieFactory()[m
