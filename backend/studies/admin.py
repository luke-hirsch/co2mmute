from django.contrib import admin

from studies.models import Participant, ResearchNote, Study, StudyGame, StudySeat


@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    search_fields = ("name",)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("code", "study", "created_at")
    list_filter = ("study",)
    search_fields = ("code",)


admin.site.register(StudyGame)
admin.site.register(StudySeat)


@admin.register(ResearchNote)
class ResearchNoteAdmin(admin.ModelAdmin):
    list_display = ("study", "author", "about_date", "created_at")
    list_filter = ("study",)
