def request_eval_context(request):
    """The "demander un avis" CTA must be disabled on the actual action form page."""

    context = {"is_request_btn_disabled": request.path.startswith("/avis/formulaire/")}
    return context
