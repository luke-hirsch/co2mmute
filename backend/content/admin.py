from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from .models import Page, ContentBlock, ContentBlockImage, ContentBlockBody

# Register your models here.
class PageContentBlockInline(admin.StackedInline):
    model = ContentBlock
    extra = 0   
    ordering = ("order","id")
    show_change_link = True

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    inlines = [PageContentBlockInline]
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
            "<div style='margin: 0, line-height: 1.25; white-space: nowrap;'>"
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
    

class ContentBlockBodyInline(admin.StackedInline):
    model = ContentBlockBody
    extra = 0
    max_num = 1

class ContentBlockImageInline(admin.StackedInline):
    model = ContentBlockImage
    extra = 0
    max_num = 3

@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    inlines = [ContentBlockBodyInline, ContentBlockImageInline]
    list_display = ("page", "key", "order", "title")
    search_fields = ("page__key", "title", "key")
    list_filter = ("page",)
    ordering = ("page", "order", "id")

    def get_model_perms(self, request):
        # Hide ContentBlock from the admin index page
        return {}