from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


class UsernameOrEmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Benutzername oder E-Mail")

    def clean(self):
        username_or_email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username_or_email and password and "@" in username_or_email:
            user_model = get_user_model()
            try:
                user = user_model._default_manager.get(email__iexact=username_or_email)
            except (user_model.DoesNotExist, user_model.MultipleObjectsReturned):
                pass
            else:
                self.cleaned_data["username"] = getattr(user, user_model.USERNAME_FIELD)

        return super().clean()


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="E-Mail-Adresse", required=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
