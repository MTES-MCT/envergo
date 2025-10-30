from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404

from envergo.geodata.models import Department


class InstructorDepartmentAuthorised(AccessMixin):
    """Authorize user according to project department"""

    department = None

    def get_departement(self, **kwargs):
        """Get department from kwargs if available"""
        return get_object_or_404(Department, department=self.kwargs["department"])

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Find department if exists and set object department attribute
        if not self.department:
            self.department = self.get_departement(**kwargs)

        if (
            not request.user.is_superuser
            and self.department not in request.user.departments.all()
        ):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
