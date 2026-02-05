from django.contrib import admin
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html, format_html_join
from .models import Page, ContentBlock, ContentBlockColumn
from adminsortable2.admin import SortableStackedInline, SortableAdminBase

# Register your models here.

class ContentBlockInline(SortableStackedInline):
    model = ContentBlock
    extra = 0   
    fields = ("order", "key" , "title")
    ordering = ("order","id")
    show_change_link = True


@admin.register(Page)
class PageAdmin(SortableAdminBase,admin.ModelAdmin):
    inlines = [ContentBlockInline]
    list_display = ("key", "title", "content_blocks_list", "is_published", "updated_at")
    search_fields = ("key", "title", "heading")
    list_filter = ("is_published", "created_at", "updated_at")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)  
        return qs.prefetch_related("sections")
    
    @admin.display(description="Content Blocks")
    def content_blocks_list(self, obj):
        blocks = list(obj.sections.all().order_by("order","id"))
        
        if not blocks:
            return "-"
        
        def block_change_url(block:ContentBlock) -> str:
            return reverse("admin:content_contentblock_change", args=[block.id])
        
        items = format_html_join(
            "",
            "<div style='margin: 0; line-height: 1.25; white-space: nowrap;'>"
            "<a href='{}'>{} - {}</a>"
            "</div>",
            (
                (
                    block_change_url(block),
                    block.order,
                    (block.title or block.key or "(no title)"),
                )
                for block in blocks
            ),
        )
        return format_html("<div style='min-width: 220px;'>{}</div>", items)

    def save_model(self, request, obj, form, change):
        # no object pk means this is a new object, so set created_by
        if not obj.pk:
            obj.created_by = request.user
        
        # always set updated_by to the current user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    

class ContentBlockColumnInline(SortableStackedInline):
    model = ContentBlockColumn
    extra = 0
    fields = ("order", "kind",  "width", "title", "body", "image", "alt_text", "caption", "img_width", "img_height")
    readonly_fields = ("img_width", "img_height")
    ordering = ("order", "id")

    def save_model(self, request, obj, form, change):
        
        # set updated_by of the related page to the current user
        obj.content_block.page.updated_by = request.user
        obj.content_block.page.save(update_fields=["updated_by"])
        super().save_model(request, obj, form, change)

@admin.register(ContentBlock)
class ContentBlockAdmin(SortableAdminBase, admin.ModelAdmin):

    list_display = ("page", "order", "key", "title")
    list_filter = ("page",)
    search_fields = ("page__key", "title", "key")
    ordering = ("page", "order", "id")

    inlines = [ContentBlockColumnInline]

    def get_model_perms(self, request):
        # Hide ContentBlock from the admin index page
        return {}
    
    def save_model(self, request, obj, form, change):
        # set updated_by of the related page to the current user
        obj.page.updated_by = request.user
        obj.page.save(update_fields=["updated_by"])
        super().save_model(request, obj, form, change)
        
