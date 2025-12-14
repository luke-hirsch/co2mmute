from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


class SignupForm(forms.ModelForm):
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = get_user_model()
        fields = ("username", "email")

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("Please enter a username.")
        user_model = self._meta.model
        if user_model.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            raise forms.ValidationError("Please enter an email address.")
        user_model = self._meta.model
        if user_model.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email address is already in use.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password") or ""
        prospective_user = self._meta.model(
            username=self.cleaned_data.get("username", ""),
            email=self.cleaned_data.get("email", ""),
        )
        try:
            validate_password(password, user=prospective_user)
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.username.strip()
        user.email = user.email.strip()
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
