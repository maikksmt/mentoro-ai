import os
import uuid
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_protect
from django.contrib.admin.views.decorators import staff_member_required
from filer.models import Image as FilerImage


@staff_member_required
@csrf_protect
def tinymce_upload(request: HttpRequest):
    if request.method != "POST" or "file" not in request.FILES:
        return JsonResponse({"error": "Invalid request"}, status=400)

    f = request.FILES["file"]
    name = f"{uuid.uuid4().hex}_{f.name}"
    rel_path = os.path.join("tinymce", name)
    saved_path = default_storage.save(rel_path, f)
    url = default_storage.url(saved_path)
    return JsonResponse({"location": url})


@staff_member_required
def tinymce_image_list(request):
    items = []
    for img in FilerImage.objects.order_by("-modified_at")[:200]:
        items.append({"title": img.label or img.original_filename, "value": img.url})
    return JsonResponse(items, safe=False)
