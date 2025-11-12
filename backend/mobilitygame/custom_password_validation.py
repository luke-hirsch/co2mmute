from django.core.exceptions import ValidationError


class SpecialCharValidator:
    def validate(self, password, user=None):
        if not any(char in "!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~" for char in password):
            raise ValidationError(
                "The password must contain at least one special character.",
                code="password_no_special",
            )

    def get_help_text(self):
        return "Your password must contain at least one special character."


class UppercaseValidator:
    def validate(self, password, user=None):
        if not any(char.isupper() for char in password):
            raise ValidationError(
                "The password must contain at least one uppercase letter.",
                code="password_no_upper",
            )

    def get_help_text(self):
        return "Your password must contain at least one uppercase letter."


class NumericValidator:
    def validate(self, password, user=None):
        if not any(char.isdigit() for char in password):
            raise ValidationError(
                "The password must contain at least one numeric digit.",
                code="password_no_number",
            )

    def get_help_text(self):
        return "Your password must contain at least one numeric digit."
