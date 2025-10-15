import uuid
from datetime import date
from typing import Literal

from django import template
from django.template import TemplateDoesNotExist
from django.template.defaultfilters import date as date_filter
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from envergo.hedges.models import TO_PLANT, TO_REMOVE
from envergo.petitions.models import DECISIONS, STAGES
from envergo.petitions.regulations import get_instructor_view_context

register = template.Library()


@register.simple_tag()
def criterion_instructor_side_nav(regulation, criterion):
    """Render the side navigation of the instructor view for a criterion."""
    template = (
        f"haie/petitions/{regulation.slug}/{criterion.slug}_instructor_side_nav.html"
    )
    try:
        return render_to_string(
            template,
        )
    except TemplateDoesNotExist:
        return ""


@register.simple_tag(takes_context=True)
def instructor_view_part(
    context,
    part_name: Literal[
        "instructor_result_details",
        "plantation_condition_details",
        "key_elements",
        "instruction_guidelines",
    ],
    regulation,
    project,
    moulinette,
    criterion=None,
):
    """Render a specific part of the instructor view for a criterion."""

    context_dict = context.flatten()

    if criterion is None:
        template = f"haie/petitions/{regulation.slug}/{part_name}.html"
        for regulation_criterion in regulation.criteria.all():
            context_dict.update(
                get_instructor_view_context(
                    regulation_criterion.get_evaluator(), project, moulinette
                )
            )
    else:
        template = f"haie/petitions/{regulation.slug}/{criterion.slug}_{part_name}.html"
        context_dict.update(
            get_instructor_view_context(criterion.get_evaluator(), project, moulinette)
        )

    try:
        return render_to_string(
            template,
            context=context_dict,
        )
    except TemplateDoesNotExist:
        return ""


@register.simple_tag
def regulation_plantation_conditions(plantation_evaluation, regulation):
    """Render the subset of plantation conditions related to a given regulation."""

    condition_to_display = []
    for condition in plantation_evaluation.conditions:
        for criterion in regulation.criteria.all():
            if (
                condition.criterion_evaluator == criterion.get_evaluator()
                and condition.must_display()
            ):
                condition_to_display.append(condition)

    template = "hedges/_plantation_conditions.html"
    return render_to_string(
        template,
        context={
            "conditions": condition_to_display,
        },
    )


@register.simple_tag
def regulation_has_condition_to_display(plantation_evaluation, regulation):
    """Check if there are any plantation conditions to display for a given regulation."""
    for condition in plantation_evaluation.conditions:
        for criterion in regulation.criteria.all():
            if (
                condition.criterion_evaluator == criterion.get_evaluator()
                and condition.must_display()
            ):
                return True
    return False


@register.simple_tag
def ds_sender_category(message_sender_email, sender_emails_categories):
    """Return appropriate class according to the sender"""

    for key, item in sender_emails_categories.items():
        if isinstance(item, list):
            if message_sender_email in item:
                return key
        else:
            if message_sender_email == item:
                return key

    return "instructor"


@register.filter
def display_property(hedge_property):
    return bool(hedge_property[TO_REMOVE] or hedge_property[TO_PLANT])


@register.filter
def sum_degradee_and_buissonnante(dict_by_type):
    """Sum the values of 'degradee' and 'buissonnante' types in a dictionary."""
    return dict_by_type.get("degradee", 0) + dict_by_type.get("buissonnante", 0)


@register.filter
def format_ds_number(ds_number):
    s = str(ds_number)
    return f"{s[:4]}-{s[4:]}" if len(s) >= 8 else ds_number


@register.filter
def stage_badge(stage):
    color_map = {
        STAGES.to_be_processed: "pink-tuile",
        STAGES.instruction_d: "blue-cumulus",
        STAGES.instruction_a: "blue-cumulus",
        STAGES.instruction_h: "blue-cumulus",
        STAGES.preparing_decision: "blue-cumulus",
        STAGES.notification: "blue-cumulus",
        STAGES.closed: None,
    }
    label_map = {
        STAGES.instruction_h: "Instruction hors r. unique",
    }

    color = color_map.get(stage, None)
    label = label_map.get(stage, dict(STAGES).get(stage, stage))

    return mark_safe(
        f"""<p class="fr-badge {f'fr-badge--{color}' if color else ''} fr-badge--sm">
                          {label}
                        </p>"""
    )


@register.filter
def decision_badge(decision, light_version=False):
    class_map = {
        DECISIONS.unset: None,
        DECISIONS.express_agreement: "fr-badge--success",
        DECISIONS.tacit_agreement: "fr-badge--success",
        DECISIONS.opposition: "fr-badge--error",
        DECISIONS.dropped: "fr-icon-folder-2-fill fr-badge--icon-left",
    }

    css_class = class_map.get(decision, None)
    label = dict(DECISIONS).get(decision, decision)
    uid = str(uuid.uuid4())

    if light_version:
        return (
            mark_safe(
                f"""
                    <p class="fr-badge icon-only-badge {css_class}" aria-describedby="{uid}"></p>
                    <span class="fr-tooltip fr-placement" id="{uid}" role="tooltip"> {label} </span>
            """
            )
            if css_class
            else "-"
        )
    else:
        return mark_safe(
            f"""<p class="fr-badge fr-badge--sm fr-badge--no-icon {css_class if css_class else ''}">
                          {label}
                        </p>"""
        )


@register.filter
def display_due_date(due_date, display_days_left=True):
    if not due_date or not isinstance(due_date, date):
        return mark_safe('<span class="days-left">Non renseignée</span>')

    days_left = (due_date - date.today()).days
    if days_left >= 7:
        icon_part = '<span class="fr-icon-timer-line"></span>'
    elif days_left >= 0:
        icon_part = '<span class="fr-icon-hourglass-2-fill fr-label--warning"></span>'
    else:
        icon_part = '<span class="fr-icon-warning-fill fr-label--error"></span>'

    date_part = f"""<span class="due-date">
                {icon_part}
                {date_filter(due_date, "SHORT_DATE_FORMAT")}
              </span><br/>"""

    if not display_days_left:
        days_left_part = ""
    elif days_left >= 2:
        days_left_part = f'<span class="days-left">{days_left} jours restants</span>'
    elif days_left >= 0:
        days_left_part = f'<span class="days-left">{days_left} jour restant</span>'
    elif days_left >= -1:
        days_left_part = (
            f'<span class="days-left">Dépassée depuis {abs(days_left)} jour</span>'
        )
    elif days_left:
        days_left_part = (
            f'<span class="days-left">Dépassée depuis {abs(days_left)} jours</span>'
        )
    else:
        days_left_part = ""

    return mark_safe(date_part + days_left_part)
