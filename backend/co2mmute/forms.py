from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
import logging

logger = logging.getLogger()


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
        if not user_model:
            logger.error("Signup Form: User Model not found")
            raise ObjectDoesNotExist("User Model not found")
        if user_model.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            raise forms.ValidationError("Please enter an email address.")
        user_model = self._meta.model
        if not user_model:
            logger.error("Signup Form: User Model not found")
            raise ObjectDoesNotExist("User Model not found")
        if user_model.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email address is already in use.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get("password") or ""
        if not self._meta.model:
            logger.error("Signup Form: User Model not found")
            raise ObjectDoesNotExist("User Model not found")
        prospective_user = self._meta.model(
            username=self.cleaned_data.get("username", ""),
            email=self.cleaned_data.get("email", ""),
        )
        try:
            validate_password(password, user=prospective_user)
        except DjangoValidationError as exc:
            raise forms.ValidationError(str(exc.messages))
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.username.strip()
        user.email = user.email.strip()
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    """The host edits their own account on /accounts/profile/.

    Not SignupForm with the password taken out. Its cleaners ask whether
    *anybody* holds this username, and on an update the answer is always yes
    — you do — so it would refuse every save that left the name alone. Every
    query here excludes the row being edited.
    """

    class Meta:
        model = get_user_model()
        fields = ("first_name", "username", "email")
        labels = {
            "first_name": "Anzeigename",
            "username": "Benutzername",
            "email": "E-Mail-Adresse",
        }
        help_texts = {
            "first_name": "So begrüßt dich die Seite. Darf leer bleiben.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # styling, as in GameSessionCreateForm
        base_class = (
            "block w-full rounded-md bg-white px-3 py-2 text-base text-gray-900 "
            "outline outline-1 outline-gray-300 focus:outline-2 "
            "focus:outline-indigo-600 dark:bg-white/5 dark:text-white "
            "dark:outline-white/10"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", base_class)

        self.fields["first_name"].required = False
        self.fields["email"].required = True
        # Django ships both of these in English, and they render on a German
        # page: the help text under the field, the validator on a bad name.
        self.fields["username"].help_text = ""
        self.fields["username"].validators = [
            UnicodeUsernameValidator(
                message=(
                    "Ein Benutzername darf nur Buchstaben, Ziffern und "
                    "@/./+/-/_ enthalten."
                )
            )
        ]

    def _held_by_somebody_else(self, field_name, value):
        user_model = self._meta.model
        if not user_model:
            logger.error("Profile Form: User Model not found")
            raise ObjectDoesNotExist("User Model not found")
        others = user_model.objects.filter(**{f"{field_name}__iexact": value})
        if self.instance.pk is not None:
            others = others.exclude(pk=self.instance.pk)
        return others.exists()

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("Bitte gib einen Benutzernamen ein.")
        if self._held_by_somebody_else("username", username):
            raise forms.ValidationError(
                "Dieser Name ist schon vergeben. Wähle einen anderen."
            )
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            raise forms.ValidationError("Bitte gib eine E-Mail-Adresse ein.")
        if self._held_by_somebody_else("email", email):
            raise forms.ValidationError("Diese Adresse gehört schon zu einem Konto.")
        return email
