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
    return hedge_property[TO_REMOVE] or hedge_property[TO_PLANT]
