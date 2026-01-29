from django.contrib import admin
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils.html import format_html, format_html_join
from .models import Page, ContentBlock, TextColumn, ImageColumn, ContentBlockColumn

# Register your models here.

class OrderDropdownFormset(BaseInlineFormSet):
    
    def _used_orders_in_block(self, exclude_pk = None) -> set[int]:
        qs = ContentBlockColumn.objects.filter(content_block=self.instance)

        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        
        return set(qs.values_list("order", flat = True))
    
    def add_fields(self, form, index):
        super().add_fields(form, index)

        used = self._used_orders_in_block(exclude_pk=form.instance.pk)

        current = form.instance.order if form.instance.pk else None

        next_slot = (max(used) +1) if used else 0

        current_set = {current} if current is not None else set()
        max_choice = max(used | {next_slot} |  current_set)
       
        choices = []
        for i in range(0, max_choice +1):
            if i == current or i not in used:
                choices.append((i, str(i)))

        form.fields["order"] = forms.TypedChoiceField(
            choices=choices,
            coerce=int,
            required = True, 
            label=form.fields["order"].label,
            help_text=form.fields["order"].help_text,
        )

class ContentBlockInline(admin.StackedInline):
    model = ContentBlock
    extra = 0   
    fields = ("order", "key" , "title")
    ordering = ("order","id")
    show_change_link = True

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
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
    

class TextColumnInline(admin.StackedInline):
    model = TextColumn
    extra = 0
    formset = OrderDropdownFormset
    fields = ("order", "width", "title", "body")
    ordering = ("order", "id")

class ImageColumnInline(admin.StackedInline):
    model = ImageColumn
    extra = 0
    formset = OrderDropdownFormset
    fields = ("order", "width", "image", "alt_text", "caption", "img_width", "img_height")
    readonly_fields = ("img_width", "img_height")
    ordering = ("order", "id")  

@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):

    list_display = ("page", "order", "key", "title")
    list_filter = ("page",)
    search_fields = ("page__key", "title", "key")
    ordering = ("page", "order", "id")

    inlines = [TextColumnInline, ImageColumnInline]

    def get_model_perms(self, request):
        # Hide ContentBlock from the admin index page
        return {}