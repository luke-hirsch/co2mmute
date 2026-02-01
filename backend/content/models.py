from django.db import models    
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django_prose_editor.fields import ProseEditorField



# Create your models here.
class Page(models.Model):

    # page info
    key = models.SlugField(unique=True)
    title = models.CharField(max_length=200, blank=True)
    heading = models.CharField(max_length=200, blank=True)
    placement = models.CharField(max_length=100, blank=True)

    # publication info 
    is_published = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # user info set automatically in admin
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        related_name="page_created",
    )

    updated_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        related_name="page_updated",
    )

    def __str__(self):
        return self.key

class ContentBlock(models.Model):
    
    # related page
    page = models.ForeignKey(
        Page, on_delete=models.CASCADE, related_name="sections"
    )

    # block info
    key = models.SlugField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0, blank=False, null=False, db_index=True)
    title = models.CharField(max_length=200, blank=True)
        
    class Meta:
        ordering = ["order"]

#        constraints = [
#            models.UniqueConstraint(
#                fields=["page", "order"],
#                name="unique_content_block_order_per_page",
#            )
#        ]

    def __str__(self):
        return f"{self.page.key} - #{self.order}"

class ContentBlockColumn(models.Model):
    
    # relation to content block
    content_block = models.ForeignKey(
        ContentBlock, on_delete=models.CASCADE, related_name="content_columns"
    )
    
    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"

    
    kind = models.CharField(max_length=10, choices=Kind.choices)
    order = models.PositiveIntegerField(default=0, db_index=True, null=False, blank=False)

    # column width in percent
    width = models.PositiveIntegerField(
        default=33, 
        help_text="Width of column in percent (1-100)",
        validators=[MinValueValidator(1), MaxValueValidator(100)],)
    
    alignment_choices = {
        "L" : "Links",
        "C" : "Zentriert",
        "R" : "Rechts",
    }

    alignment = models.CharField(
        max_length=1,
        choices=alignment_choices, 
        default="L",
        help_text="Alignment of content within the column",
    )
    
    # optional fields if kind is text
    title = models.CharField(max_length=200, blank=True)
    body = ProseEditorField(
        extensions={
            # Core text formatting
            "Bold": True,
            "Italic": True,
            "Strike": True,
            "Underline": True,
            "HardBreak": True,

            # Structure
            "BulletList": True,
            "OrderedList": True,
            "ListItem": True, # Used by BulletList and OrderedList
            "Blockquote": True,

            # Advanced extensions
            "Link": {
                "enableTarget": True,  # Enable "open in new window"
                "protocols": ["http", "https", "mailto"],  # Limit protocols
            },
            "Table": True,
            "TableRow": True,
            "TableHeader": True,
            "TableCell": True,

            # Editor capabilities
            "History": True,       # Enables undo/redo
            "HTML": True,          # Allows HTML view
            "Typographic": True,   # Enables typographic chars
        }, 
        sanitize=True,
        blank=True,
    )

    # optional fields if kind is image
    image = models.ImageField(
        upload_to="page_content/",
        blank=True,
        null=True,
        height_field="img_height",
        width_field="img_width",
        max_length=100,
    )

    caption = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(max_length=200, blank=True)

    img_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    img_width = models.PositiveIntegerField(null=True, blank=True, editable=False)

    
    class Meta:
        ordering = ["order"]
        constraints = [
#            models.UniqueConstraint(
#                fields=["content_block", "order"],
#                name="unique_column_order_per_content_block",
#            ),
            models.CheckConstraint(
                check=models.Q(width__gte=1) & models.Q(width__lte=100),
                name="column_width_between_1_and_100",
            ),
        ]

    def __str__(self):
        return f"Column #{self.order} for {self.content_block}"
    
    def clean(self):

        if not self.content_block_id:

            return 
        
            
        total = (
            ContentBlockColumn.objects
            .filter(content_block_id=self.content_block_id)
            .exclude(pk=self.pk)
            .aggregate(models.Sum("width"))["width__sum"] 
            or 0
            ) + (self.width + 0)

        if total > 100:
            raise ValidationError(
                {
                    "width": f"Total width of all columns for a content block cannot exceed 100%. Current total would be {total}%."
                }
            )
