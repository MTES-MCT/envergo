from envergo.moulinette.regulations.natura2000_haie import Natura2000Haie
from envergo.petitions.regulations import evaluator_instructors_information_getter
from envergo.petitions.services import InstructorInformation


@evaluator_instructors_information_getter(Natura2000Haie)
def n2000_haie_get_instructors_info(
    evaluator, petition_project, moulinette
) -> InstructorInformation:
    return InstructorInformation(
        slug="n2000", label="Natura 2000", key_elements=None, simulation_data=None
    )
