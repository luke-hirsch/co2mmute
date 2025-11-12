from django.contrib.auth import login, password_validation
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView
from django.core.exceptions import ValidationError

from .forms import SignUpForm, UsernameOrEmailAuthenticationForm


class IndexView(TemplateView):
    template_name = "index.html"


class AuthView(View):
    template_name = "login.html"
    success_url = reverse_lazy("index")
    login_form_class = UsernameOrEmailAuthenticationForm
    signup_form_class = SignUpForm

    def normalize_mode(self, raw_mode):
        return "signup" if raw_mode == "signup" else "login"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(request.GET.get("next") or self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(
        self, request, login_form=None, signup_form=None, mode="login"
    ):
        return {
            "login_form": login_form or self.login_form_class(request),
            "signup_form": signup_form or self.signup_form_class(),
            "mode": mode,
            "password_help_text": password_validation.password_validators_help_text_html(),
        }

    def get(self, request, *args, **kwargs):
        mode = self.normalize_mode(request.GET.get("mode"))
        context = self.get_context_data(request, mode=mode)
        context["next"] = request.GET.get("next", "")
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        mode = self.normalize_mode(request.POST.get("mode"))
        next_url = request.POST.get("next") or request.GET.get("next")

        if mode == "signup":
            signup_form = self.signup_form_class(request.POST)
            login_form = self.login_form_class(request)
            if signup_form.is_valid():
                password = str(signup_form.cleaned_data.get("password1"))
                user_candidate = signup_form.instance
                try:
                    password_validation.validate_password(password, user_candidate)
                except ValidationError as validation_error:
                    signup_form.add_error("password1", validation_error)
                    signup_form.add_error("password2", validation_error)
                else:
                    user = signup_form.save()
                    login(request, user)
                    return redirect(next_url or self.success_url)
        else:
            login_form = self.login_form_class(request, data=request.POST)
            signup_form = self.signup_form_class()
            if login_form.is_valid():
                login(request, login_form.get_user())
                return redirect(next_url or self.success_url)

        context = self.get_context_data(
            request,
            login_form=login_form,
            signup_form=signup_form,
            mode=mode,
        )
        context["next"] = next_url or ""
        return render(request, self.template_name, context)
