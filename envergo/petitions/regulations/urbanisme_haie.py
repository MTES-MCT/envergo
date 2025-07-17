from envergo.moulinette.regulations.urbanisme_haie import UrbanismeHaie
from envergo.petitions.regulations import evaluator_instructor_view_context_getter


@evaluator_instructor_view_context_getter(UrbanismeHaie)
def urbanisme_haie_instructor_view_context(evaluator, petition_project, moulinette):

    return {}
