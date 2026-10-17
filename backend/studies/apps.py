from django.apps import AppConfig


class StudiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "studies"

    @property
    def participant_code_length(self) -> int:
        from studies.models import PARTICIPANT_CODE_LENGTH

        return PARTICIPANT_CODE_LENGTH

    def ready(self):
        # The app plugs into `game` here; `game` never imports it.
        from game import research_export
        from game.codes import register_code_kind, register_look_extra

        from studies import codes, export

        research_export.register_tables(export.SCHEMA, export.write_tables)
        register_code_kind(
            self.participant_code_length,
            look=codes.look,
            take=codes.take,
            counted=True,
        )
        register_look_extra(codes.coded_study)
