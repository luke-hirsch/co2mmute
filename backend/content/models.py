from django.db import models    
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from prose.models import AbstractDocument


# Create your models here.
class Page(models.Model):

    # page info
    key = models.SlugField(unique=True)
    title = models.CharField(max_length=200, blank=True)
    heading = models.CharField(max_length=200, blank=True)

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
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200, blank=True)
        
    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.page.key} - #{self.order}"

class ContentBlockColumn(models.Model):
    
    content_block = models.ForeignKey(
        ContentBlock, on_delete=models.CASCADE, related_name="content_column"
    )

    order = models.PositiveIntegerField(default=0, help_text="Order of column left to right")

    width = models.PositiveIntegerField(
        default=33, 
        help_text="Width of column in percent (1-100)",
        validators=[MinValueValidator(1), MaxValueValidator(100)],)
    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_block", "order"],
                name="unique_column_order_per_content_block",
            ),
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

class TextColumn(ContentBlockColumn):

    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)

    def __str__(self):
        return f"Text Column #{self.order} for {self.content_block}"
    
class ImageColumn(ContentBlockColumn):

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


    def __str__(self):
        return f"Image Column #{self.order} for {self.content_block}"
