from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from content.decorators import require_group
from content.forms_editorial import (
    SubmitToReviewForm,
    ReviewUpdateForm,
    get_model_or_none,
)


def _model_from_key(key: str):
    mapping = {
        "guide": "Guide",
        "usecase": "UseCase",
        "prompt": "Prompt",
    }
    model_name = mapping.get(key)
    if not model_name:
        return None
    return get_model_or_none(model_name)


def _user_is_author_of(obj, user):
    return hasattr(obj, "author") and obj.author_id == user.id


@login_required
def my_drafts(request):
    items = []
    for key, model_name in [
        ("guide", "Guide"),
        ("usecase", "UseCase"),
        ("prompt", "Prompt"),
    ]:
        M = get_model_or_none(model_name)
        if not M:
            continue
        qs = M.objects.all()
        if hasattr(M, "author"):
            qs = qs.filter(author=request.user)
        if hasattr(M, "status"):
            qs = qs.exclude(status="published")
        items.extend([(key, x) for x in qs])
    items.sort(
        key=lambda t: getattr(t[1], "updated_at", getattr(t[1], "created_at", 0)),
        reverse=True,
    )
    context = {
        "items": items,
        "seo_title": _("Editorial – My Drafts."),
        "seo_description": _("Internal editorial area."),
    }

    return render(request, "content/editorial/my_drafts.html", context)


@login_required
def submit_to_review(request):
    """Autor reicht eigenen Entwurf zur Review ein."""
    if request.method == "POST":
        form = SubmitToReviewForm(request.POST)
        if form.is_valid():
            M = _model_from_key(form.cleaned_data["model"])
            obj = get_object_or_404(M, pk=form.cleaned_data["object_id"])
            if not _user_is_author_of(obj, request.user):
                error_message = _("Only the author can submit the article.")
                messages.error(request, error_message)
                return redirect("content:editorial:my_drafts")
            if hasattr(obj, "status"):
                obj.status = "review"
            if hasattr(obj, "editor") and not getattr(obj, "editor", None):
                pass
            obj.save()
            success_message = _("Submitted for review.")
            messages.success(request, success_message)
            return redirect("content:editorial:my_drafts")
    else:
        form = SubmitToReviewForm()

    context = {
        "form": form,
        "seo_title": _("Editorial – Submit for Review."),
        "seo_description": _("Internal editorial area"),
    }
    return render(request, "content/editorial/submit_to_review.html", context)


@require_group("editor", "admin")
def review_queue(request):
    """Editor/Admin sieht alle Items mit status=review."""
    queues = []
    for key, model_name in [
        ("guide", "Guide"),
        ("usecase", "UseCase"),
        ("prompt", "Prompt"),
    ]:
        M = get_model_or_none(model_name)
        if not M or not hasattr(M, "status"):
            continue
        qs = M.objects.filter(status="review")
        queues.append(
            (key, qs.select_related(getattr(M, "author", None) and "author" or None))
        )

    context = {
        "queues": queues,
        "seo_title": _("Editorial – Review Queue"),
        "seo_description": _("Internal editorial area"),
    }
    return render(request, "content/editorial/review_queue.html", context)


@require_group("editor", "admin")
def review_update(request):
    """Editor/Admin ändert Status, optional veröffentlicht."""
    if request.method == "POST":
        form = ReviewUpdateForm(request.POST)
        if form.is_valid():
            M = _model_from_key(form.cleaned_data["model"])
            obj = get_object_or_404(M, pk=form.cleaned_data["object_id"])
            new_status = form.cleaned_data["status"]
            if hasattr(obj, "status"):
                obj.status = new_status
            if new_status == "published":
                if (
                        hasattr(obj, "published_at")
                        and getattr(obj, "published_at") is None
                ):
                    setattr(obj, "published_at", timezone.now())
                # editor setzen, falls vorhanden
                if hasattr(obj, "editor"):
                    setattr(obj, "editor", request.user)
            elif new_status != "published" and hasattr(obj, "published_at"):
                # Zurück von published -> published_at leeren
                setattr(obj, "published_at", None)
            obj.save()
            message_success = _("Post updated.")
            messages.success(request, message_success)
            return redirect("content:content_editorial:review_queue")
    else:
        form = ReviewUpdateForm()

    context = {
        "form": form,
        "seo_title": _("Editorial – Review."),
        "seo_description": _("Internal editorial area"),
    }
    return render(request, "content/editorial/review_update.html", context)


@login_required
def register_author(request):
    author_group, _ = Group.objects.get_or_create(name="author")
    if not request.user.groups.filter(name="author").exists():
        request.user.groups.add(author_group)
    from django.contrib import messages

    messages.success(
        request, _("You are now registered as an author. Good luck with your writing!")
    )
    return redirect("content:content_editorial:my_drafts")
