from django.contrib import admin
from django.urls import path, include

from django.views.generic import TemplateView
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator


@method_decorator(login_not_required, name="dispatch")
class IndexView(TemplateView):
    template_name = "index.html"


class CustomLoginView(LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        email = (request.POST.get("email") or "").strip()

        if not username:
            form.add_error("username", "Bitte geben Sie einen Benutzernamen an.")
            return self.form_invalid(form)

        user_model = get_user_model()
        backend = settings.AUTHENTICATION_BACKENDS[0]

        if not password:
            # Guest flow: create or reuse an account without a usable password.
            try:
                user = user_model.objects.get(username=username)
                if user.has_usable_password():
                    form.add_error("username", "Dieser Benutzername ist bereits vergeben.")
                    return self.form_invalid(form)
            except user_model.DoesNotExist:
                user = user_model.objects.create(username=username)
                user.set_unusable_password()
                user.save()

            user.backend = backend
            login(request, user)
            return HttpResponseRedirect(self.get_success_url())

        if email:
            if user_model.objects.filter(username=username).exists():
                form.add_error("username", "Dieser Benutzername ist bereits vergeben.")
                return self.form_invalid(form)

            user = user_model.objects.create_user(
                username=username,
                password=password,
                email=email,
            )
            user.backend = backend
            login(request, user)
            return HttpResponseRedirect(self.get_success_url())

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(self.get_success_url())

        if not user_model.objects.filter(username=username).exists():
            form.add_error(None, "Bitte geben Sie eine E-Mail-Adresse an, um ein neues Konto zu erstellen.")
        else:
            form.add_error("password", "Ungültige Anmeldedaten.")
        return self.form_invalid(form)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("", IndexView.as_view(), name="index"),
    path("game/", include("game.urls")),
]
