from typing import Literal

from django import template
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from envergo.hedges.models import TO_PLANT, TO_REMOVE
from envergo.petitions.regulations import get_instructor_view_context

register = template.Library()


@register.simple_tag()
def criterion_instructor_side_nav(regulation, criterion):
    template = (
        f"haie/petitions/{regulation.slug}/{criterion.slug}_instructor_side_nav.html"
    )
    return render_to_string(
        template,
    )


@register.simple_tag(takes_context=True)
def criterion_instructor_view_part(
    context,
    part_name: Literal["instructor_result_details", "plantation_condition_details"],
    regulation,
    criterion,
    project,
    moulinette,
):
    template = f"haie/petitions/{regulation.slug}/{criterion.slug}_{part_name}.html"
    context_dict = context.flatten()
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
    for condition in plantation_evaluation.conditions:
        for criterion in regulation.criteria.all():
            if (
                condition.criterion_evaluator == criterion.get_evaluator()
                and condition.must_display()
            ):
                return True
    return False


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
