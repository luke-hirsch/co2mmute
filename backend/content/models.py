from django.db import models

# Create your models here.
class SiteContent(models.Model):
    key = models.SlugField(unique=True)
    title = models.CharField(max_length=200, blank=True)
    heading = models.CharField(max_length=200, blank=True)

    is_published = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="sitecontent_created",
    )
    updated_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="sitecontent_updated",
    )

    def __str__(self):
        return self.key
    

class SiteContentBlock(models.Model):
    content = models.ForeignKey(SiteContent, on_delete=models.CASCADE, related_name="sections")
    key = models.SlugField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "id"]  

    def __str__(self):
        return f"{self.content.key} - #{self.order})" 
    
