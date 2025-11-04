from django.contrib.auth.mixins import AccessMixin
from django.http import Http404
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import Department


class InstructorDepartmentAuthorised(AccessMixin):
    """Authorize user according to project department"""

    department = None

    def get_departement(self, **kwargs):
        """Get department from kwargs if available"""

        department_qs = Department.objects.defer("geometry").filter(
            department=self.kwargs["department"]
        )
        try:
            # Get the single item from the filtered queryset
            current_department = department_qs.get()
        except department_qs.model.DoesNotExist:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": department_qs.model._meta.verbose_name}
            )
        return current_department

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Find department if exists and set object department attribute
        if not self.department:
            self.department = self.get_departement(**kwargs)

        if (
            not request.user.is_superuser
            and self.department not in request.user.departments.defer("geometry").all()
        ):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
