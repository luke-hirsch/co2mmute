import logging

from django import forms
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import (
    MinimumLengthValidator,
    get_default_password_validators,
    validate_password,
)
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError

logger = logging.getLogger()

# The wording the host page's account form already uses (`serializers.py`),
# so a name is refused in the same sentence at both doors.
USERNAME_MESSAGES = {
    "required": "Bitte gib einen Benutzernamen ein.",
    "invalid": "Ein Benutzername darf nur Buchstaben, Ziffern und @/./+/-/_ enthalten.",
    "max_length": "Ein Benutzername hat höchstens 150 Zeichen.",
}
USERNAME_TAKEN = "Dieser Name ist schon vergeben. Wähle einen anderen."
EMAIL_MESSAGES = {
    "required": "Bitte gib eine E-Mail-Adresse ein.",
    "invalid": "Das sieht nicht nach einer E-Mail-Adresse aus.",
}
EMAIL_TAKEN = "Diese Adresse gehört schon zu einem Konto."


def password_rules():
    """The password rules as one German sentence, for under the field.

    The length comes off the configured `MinimumLengthValidator` rather than
    being typed here, so the sentence cannot promise 8 while the check asks 12.
    """
    min_length = next(
        (
            validator.min_length
            for validator in get_default_password_validators()
            if isinstance(validator, MinimumLengthValidator)
        ),
        None,
    )
    rules = "mit Ziffer, Groß- und Kleinbuchstaben und einem Sonderzeichen"
    if min_length:
        return f"Mindestens {min_length} Zeichen, {rules}."
    return f"{rules[0].upper()}{rules[1:]}."


def german_password_errors(error: DjangoValidationError) -> list[str]:
    """Django's password refusals, one German sentence per broken rule.

    `validate_password` raises one `ValidationError` carrying a list — one entry
    per rule — and each entry keeps its `code` and `params`. That is what makes
    this possible without switching `LANGUAGE_CODE`: Django's own German
    catalogue addresses the reader as "Sie" in places, and this project says
    "du" everywhere.

    `SignupForm` used to raise `str(exc.messages)`, which put the *repr of a
    Python list* on the page — brackets, and quotes escaped to `&#x27;`. A rule
    this does not know passes its own message through; the checks in
    `test_credentials.py` break every configured validator, so a new one that
    speaks English goes red there.
    """
    messages = []
    for item in error.error_list:
        params = item.params or {}
        if item.code == "password_too_short":
            messages.append(f"Zu kurz: mindestens {params.get('min_length', 8)} Zeichen.")
        elif item.code == "password_too_common":
            messages.append("Das ist eines der häufigsten Passwörter und schnell erraten.")
        elif item.code == "password_entirely_numeric":
            messages.append("Nur Ziffern reichen nicht.")
        elif item.code == "password_too_similar":
            messages.append("Zu nah an deinem Benutzernamen oder deiner E-Mail-Adresse.")
        else:
            messages.extend(item.messages)
    return messages


class StyledForm:
    """Every widget wears the design system's class.

    `field-input` and `field-checkbox` are defined once, in
    `static/css/custom.css`, as the Django twin of the SPA's `Input` — set
    here rather than in a template because a stock auth form renders its own
    `<input>` from `{{ field }}`. Kept out of Python class *lists* on purpose:
    Tailwind's build scans `template/`, not `.py` files, so a utility named only
    in here may never be generated.

    Django 5 adds `aria-invalid` to a field with errors by itself.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():  # type: ignore[attr-defined]
            is_box = isinstance(field.widget, forms.CheckboxInput)
            field.widget.attrs.setdefault("class", "field-checkbox" if is_box else "field-input")


class GermanNewPasswordMixin:
    """The two new-password fields, for reset and change alike."""

    error_messages = {
        "password_mismatch": "Die beiden Passwörter sind nicht gleich.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        first = self.fields["new_password1"]  # type: ignore[attr-defined]
        second = self.fields["new_password2"]  # type: ignore[attr-defined]
        first.label = "Neues Passwort"
        first.help_text = password_rules()
        first.error_messages["required"] = "Bitte gib ein neues Passwort ein."
        second.label = "Noch einmal"
        second.help_text = "Zur Kontrolle, damit sich kein Tippfehler einschleicht."
        second.error_messages["required"] = "Bitte gib das neue Passwort noch einmal ein."

    def validate_password_for_user(self, user, password_field_name="password2"):
        password = self.cleaned_data.get(password_field_name)  # type: ignore[attr-defined]
        if not password:
            return
        try:
            validate_password(password, user)
        except DjangoValidationError as error:
            for message in german_password_errors(error):
                self.add_error(password_field_name, message)  # type: ignore[attr-defined]


class LoginForm(StyledForm, auth_forms.AuthenticationForm):
    """The login, in German, with a real "Angemeldet bleiben".

    One refusal for a wrong password and an unknown name alike, so the page
    cannot be used to find out whether an account exists. The stock form has
    that property too; it only never showed the sentence.
    """

    remember_me = forms.BooleanField(required=False, label="Angemeldet bleiben")

    error_messages = {
        "invalid_login": (
            "Benutzername oder Passwort stimmen nicht. "
            "Groß- und Kleinschreibung zählt bei beiden."
        ),
        "inactive": "Dieses Konto gibt es nicht mehr.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Benutzername"
        self.fields["username"].error_messages["required"] = USERNAME_MESSAGES["required"]
        self.fields["password"].label = "Passwort"
        self.fields["password"].error_messages["required"] = "Bitte gib dein Passwort ein."


class SignupForm(StyledForm, forms.ModelForm):
    password = forms.CharField(
        label="Passwort",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        error_messages={"required": "Bitte gib ein Passwort ein."},
    )

    class Meta:
        model = get_user_model()
        fields = ("username", "email")
        labels = {"username": "Benutzername", "email": "E-Mail-Adresse"}
        help_texts = {
            "username": "Damit meldest du dich an. Mitspielende sehen ihn nicht.",
            "email": (
                "Nur für ein vergessenes Passwort. Wir schreiben dir sonst nie."
            ),
        }
        error_messages = {"username": USERNAME_MESSAGES, "email": EMAIL_MESSAGES}
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "username"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `User.email` is `blank=True`, so the model form would call it
        # optional. It is not: it is the only way back into a lost account.
        self.fields["email"].required = True
        self.fields["password"].help_text = password_rules()

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError(USERNAME_MESSAGES["required"])
        user_model = self._meta.model
        if not user_model:
            logger.error("Signup Form: User Model not found")
            raise ObjectDoesNotExist("User Model not found")
        if user_model.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(USERNAME_TAKEN)
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            raise forms.ValidationError(EMAIL_MESSAGES["required"])
        user_model = self._meta.model
        if not user_model:
            logger.error("Signup Form: User Model not found")
            raise ObjectDoesNotExist("User Model not found")
        if user_model.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(EMAIL_TAKEN)
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
            raise forms.ValidationError(german_password_errors(exc))
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.username.strip()
        user.email = user.email.strip()
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ResetRequestForm(StyledForm, auth_forms.PasswordResetForm):
    """"Passwort vergessen?" — the address the link goes to."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        email = self.fields["email"]
        email.label = "E-Mail-Adresse"
        email.help_text = "Die Adresse, mit der du dein Konto angelegt hast."
        email.error_messages.update(EMAIL_MESSAGES)


class NewPasswordForm(StyledForm, GermanNewPasswordMixin, auth_forms.SetPasswordForm):
    """The form the reset link opens."""


class ChangePasswordForm(StyledForm, GermanNewPasswordMixin, auth_forms.PasswordChangeForm):
    """"Passwort ändern" from the host page — asks for the old one first."""

    error_messages = {
        **GermanNewPasswordMixin.error_messages,
        "password_incorrect": "Das bisherige Passwort stimmt nicht.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        old = self.fields["old_password"]
        old.label = "Bisheriges Passwort"
        old.error_messages["required"] = "Bitte gib dein bisheriges Passwort ein."


class AccountDeleteForm(StyledForm, forms.Form):
    """Re-authentication before the account goes.

    The host machine stands in a classroom, often projected and often still
    logged in — the password is what keeps a passing student from pressing
    this. The confirm page of its own is the second guard.
    """

    password = forms.CharField(
        label="Passwort",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text="Zur Sicherheit, falls jemand anders an deinem Rechner sitzt.",
        error_messages={"required": "Bitte gib zur Bestätigung dein Passwort ein."},
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data.get("password") or ""
        if self.user is None or not self.user.check_password(password):
            raise forms.ValidationError("Das stimmt nicht. Versuch es noch einmal.")
        return password
