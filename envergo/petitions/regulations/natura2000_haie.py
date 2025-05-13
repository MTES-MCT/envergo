from envergo.moulinette.regulations.natura2000_haie import Natura2000Haie
from envergo.petitions.regulations import register_instructors_information
from envergo.petitions.services import InstructorInformation


@register_instructors_information(Natura2000Haie)
def n2000_haie_get_instructors_info(
    evaluator, petition_project, moulinette
) -> InstructorInformation:
    return InstructorInformation(
        slug="n2000", label="Natura 2000", items=[], details=[]
    )
