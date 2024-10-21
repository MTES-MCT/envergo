from django.utils.translation import gettext_lazy as _


def request_eval_context(request):
    context = {}
    if request.path.startswith(f"/avis/{_("form/")}"):
        context["is_request_btn_disabled"] = True
    return context
