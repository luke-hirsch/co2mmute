"""Facts the legal pages quote, read from the code so a page cannot drift."""

from django.apps import apps


def code_lengths() -> dict[str, int] | None:
    """The three code lengths, or None while the study app is off.

    A game id, a seat code and a participant code differ by length alone, which
    is how the privacy page tells them apart. The study app is asked through
    its AppConfig: nothing here imports it.
    """
    if not apps.is_installed("studies"):
        return None

    from game.models import GameSession
    from game.seats import CODE_LENGTH

    return {
        "game_id": GameSession._meta.get_field("game_id").max_length,
        "seat": CODE_LENGTH,
        "participant": apps.get_app_config("studies").participant_code_length,
    }
