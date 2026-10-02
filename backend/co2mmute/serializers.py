"""What the host may change about their own account."""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers

logger = logging.getLogger(__name__)


class HostAccountSerializer(serializers.ModelSerializer):
    """very slim:  `first_name`, `username`, `email`"""

    class Meta:
        model = get_user_model()
        fields = ("first_name", "username", "email")
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": True},
            "username": {
                "required": True,
                "validators": [
                    # Django's own message is English and it renders on a
                    # German page.
                    UnicodeUsernameValidator(
                        message=(
                            "Ein Benutzername darf nur Buchstaben, Ziffern "
                            "und @/./+/-/_ enthalten."
                        )
                    )
                ],
                "error_messages": {
                    "required": "Bitte gib einen Benutzernamen ein.",
                    "blank": "Bitte gib einen Benutzernamen ein.",
                },
            },
            "email": {
                "required": True,
                "allow_blank": False,
                "error_messages": {
                    "required": "Bitte gib eine E-Mail-Adresse ein.",
                    "blank": "Bitte gib eine E-Mail-Adresse ein.",
                    "invalid": "Das sieht nicht nach einer E-Mail-Adresse aus.",
                },
            },
        }

    def _held_by_somebody_else(self, field_name: str, value: str) -> bool:
        user_model = self.Meta.model
        others = user_model.objects.filter(**{f"{field_name}__iexact": value})
        if self.instance is not None and self.instance.pk is not None:
            others = others.exclude(pk=self.instance.pk)
        return others.exists()

    def validate_username(self, value: str) -> str:
        username = (value or "").strip()
        if not username:
            raise serializers.ValidationError("Bitte gib einen Benutzernamen ein.")
        if self._held_by_somebody_else("username", username):
            raise serializers.ValidationError(
                "Dieser Name ist schon vergeben. Wähle einen anderen."
            )
        return username

    def validate_email(self, value: str) -> str:
        email = (value or "").strip()
        if not email:
            raise serializers.ValidationError("Bitte gib eine E-Mail-Adresse ein.")
        if self._held_by_somebody_else("email", email):
            raise serializers.ValidationError(
                "Diese Adresse gehört schon zu einem Konto."
            )
        return email

    def validate_first_name(self, value: str) -> str:
        return (value or "").strip()
