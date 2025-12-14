from django.core.exceptions import ValidationError


class CustomPasswordValidator:
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

    def get_help_text(self):
        return (
            "Your password must include at least one digit, one lowercase and uppercase "
            "letter, and one special character."
        )


def game_map_clean(version_game_maps, base_game_map):
    for version_game_map in version_game_maps:
        if version_game_map != base_game_map:
            raise ValidationError(
                f"MapVersion's GameMap {version_game_map} does not match Node's GameMap {base_game_map}"
            )
