from django.views.generic import TemplateView


class IndexView(TemplateView):
    template_name = "index.html"


class SpaView(TemplateView):
    template_name = ""


class SignUpView(TemplateView):
    template_name = "registration/signup.html"


class DsgvoView(TemplateView):
    template_name = "legal/dsgvo.html"


class ImpressumView(TemplateView):
    template_name = "legal/impressum.html"
