from django import template
from django.template.loader import render_to_string

from envergo.hedges.models import TO_PLANT, TO_REMOVE
from envergo.petitions.regulations import get_instructor_view_context

register = template.Library()


@register.simple_tag(takes_context=True)
def criterion_instructor_view(context, regulation, criterion, project, moulinette):
    template = f"haie/petitions/{regulation.slug}/{criterion.slug}_instructor.html"
    context_dict = context.flatten()
    context_dict.update(
        get_instructor_view_context(criterion.get_evaluator(), project, moulinette)
    )

    return render_to_string(
        template,
        context=context_dict,
    )


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
