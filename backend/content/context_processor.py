from .models import NavigationItem, Page

# return navigation items necessary for base template
def navigation_items_processor(request):
    
    # Get all navigation items and prefetch related page data to minimize queries
    nav_items = NavigationItem.objects.select_related("page").all()
    
    # Organize items by location and parent-child relationships
    navigation = {}
    for item in nav_items:
        location = item.location
        if location not in navigation:
            navigation[location] = []
        
        if item.parent is None:
            # Top-level item
            navigation[location].append({
                "order": item.order,
                "label": item.label,
                "page_key": item.page.key if item.page else None,
                "children": []
            })
        else:
            # Child item, find its parent in the current location
            for parent_item in navigation[location]:
                if parent_item["order"] == item.parent.order:
                    parent_item["children"].append({
                        "order": item.order,
                        "label": item.label,
                        "page_key": item.page.key if item.page else None,
                    })
                    break
    
    return {"navigation_items": navigation}