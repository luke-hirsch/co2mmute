from django.db import models    
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django_prose_editor.fields import ProseEditorField

class NavigationItem(models.Model):
    
    LOCATION_CHOICES = [
        ("header", "Header"),
        ("footer", "Footer"),
        ("sidebar", "Sidebar"),
    ]
    # header, footer, sidebar, etc.
    location = models.CharField(max_length=100 , choices=LOCATION_CHOICES, blank=True)

    # page blank means this item can be used as menu container 
    page = models.ForeignKey(
        "Page", 
        on_delete=models.CASCADE, 
        related_name="navigation_items", 
        null=True, 
        blank=True
        )

    # top-level item in the menu if blank (meaning: page and parent can't both be blank!)
    parent = models.ForeignKey(
        "self", 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name="children"
        )
    
    
    label = models.CharField(max_length=100, blank=False, help_text="Label to display in the navigation menu")

    # ordering field for manual sorting of items within the same level and location
    order = models.PositiveIntegerField(default=0, blank=False, null=False, db_index=True )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        page_key = self.page.key if self.page else "No page"
        return f"NavItem: {self.label} ({page_key})"
    


    def clean(self):
        super().clean()

        # if child but location missing just take location from parent
        if self.parent and not self.location:
            self.location = self.parent.location

        # prevent circular references
        parent = self.parent
        while parent is not None:
            if parent == self:
                raise ValidationError("A navigation item cannot be its own ancestor.")
            parent = parent.parent
        # make sure parent and child items have the same location
        if self.parent and self.parent.location != self.location:
            raise ValidationError("Parent navigation item must have the same location.")

    # submenu container rule:
    # if navitem already has children in DB, it must not have a page assigned
        if self.page and self.pk:
            if self.children.exists():
                raise ValidationError("A menu container cannot also link to a page.")

    

# Create your models here.
class Page(models.Model):

    # page info
    key = models.SlugField(unique=True, help_text="Unique identifier for the page (used in URLs)")
    title = models.CharField(max_length=200, blank=True, help_text="Title of the page")
    heading = models.CharField(max_length=200, blank=True, help_text="Heading displayed on the page")

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

    # column width in percent and alignment
    width = models.PositiveIntegerField(
        default=33, 
        help_text="Width of column in percent (1-100)",
        validators=[MinValueValidator(1), MaxValueValidator(100)],)
    
    # optional fields if kind is text
    title = models.CharField(max_length=200, blank=True, help_text="Optional Heading for the text column")
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
            "TextStyle": True,

            # ✨ Text alignment
            "TextAlign": {
                "types": ["heading", "paragraph"],   # Which blocks can be aligned
                "alignments": ["left", "center", "right", "justify"],
            },

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
    alignment = models.CharField(
        max_length=20,
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],        default="center",
        help_text="Image and heading alignment within the column",
    )

    # automatically set image dimensions
    img_height = models.PositiveIntegerField(null=True, blank=True, editable=False, help_text="Height of the uploaded image in pixels")
    img_width = models.PositiveIntegerField(null=True, blank=True, editable=False, help_text="Width of the uploaded image in pixels")

    
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
