from .models import NavigationItem

def navigation_items_processor(request):
    qs = (
        NavigationItem.objects
        .select_related("page", "parent")
        .order_by("location", "parent_id", "parent__order", "order")
    )

    navigation = {}
    top_by_id = {}

    for item in qs:
        navigation.setdefault(item.location, [])
        if item.parent_id is None:
            top_item = {
                "id": item.id,
                "order": item.order,
                "label": item.label,
                "page_key": item.page.key if item.page else None,
                "children": [],
            }
            navigation[item.location].append(top_item)
            top_by_id[item.id] = top_item

    for item in qs:
        if item.parent_id is not None:
            parent = top_by_id.get(item.parent_id)
            if parent is not None:
                parent["children"].append({
                    "id": item.id,
                    "order": item.order,
                    "label": item.label,
                    "page_key": item.page.key if item.page else None,
                })

    return {"navigation_items": navigation}
