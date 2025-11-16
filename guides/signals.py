# guides/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django_fsm import can_proceed

from .models import Guide, GuideSection


def _move_parent_to_review(guide, note):
    if not guide:
        return
    if getattr(guide, "status", None) != getattr(Guide, "STATUS_PUBLISHED", "published"):
        return
    if hasattr(guide, "move_to_review") and can_proceed(guide.move_to_review):
        guide.move_to_review(note=note)
        guide.save()


@receiver(post_save, sender=GuideSection)
def section_saved(sender, instance, **kwargs):
    _move_parent_to_review(getattr(instance, "guide", None), _("Auto: Change to GuideSection (save)"))


@receiver(post_delete, sender=GuideSection)
def section_deleted(sender, instance, **kwargs):
    _move_parent_to_review(getattr(instance, "guide", None), _("Auto: Change to GuideSection (delete)"))
