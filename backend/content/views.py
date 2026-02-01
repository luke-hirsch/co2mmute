# from django.shortcuts import render
from collections import defaultdict
from django.shortcuts import render, get_object_or_404
from django.views.generic import DetailView
from django.db.models import Prefetch
from .models import Page, ContentBlock, ContentBlockColumn

# Create your views here.
class PageDetailView(DetailView):

    model = Page
    template_name = "static_content_page.html"
    context_object_name = "page"
    slug_field = "key"
    slug_url_kwarg = "key"

    def get_queryset(self):
        qs = super().get_queryset()

        # only published pages if not staff
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            qs = qs.filter(is_published=True)


        # return qs with prefetches for correct ordering
        return qs.prefetch_related(
            Prefetch(
                "sections", 
                queryset=ContentBlock.objects.order_by("order").prefetch_related(
                    Prefetch(
                        "content_columns",
                        queryset=ContentBlockColumn.objects.order_by("order"),
                    )
                ),
            )
        )
    