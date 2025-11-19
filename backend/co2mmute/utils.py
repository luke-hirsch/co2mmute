from django.contrib.auth.password_validation import PasswordValidator
from django.core.exceptions import ValidationError


class CustomPasswordValidator(PasswordValidator):
    def validate(self, password, user=None):
        errors = []

        if not any(char.isdigit() for char in password):
            errors.append("The password must contain at least one digit.")
        if not any(char.isalpha() and char.islower() for char in password) or not any(
            char.isalpha() and char.isupper() for char in password
        ):
            errors.append(
                "The password must contain both lowercase and uppercase letters."
            )
        if not any(not char.isalnum() for char in password):
            errors.append("The password must contain at least one special character.")

        if errors:
            raise ValidationError(errors)
