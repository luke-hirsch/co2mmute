from django.db import models


# Create your models here.
class GameMap(models.Model):
    map_name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.map_name
