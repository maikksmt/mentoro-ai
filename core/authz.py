import rules
from django.conf import settings


def _is_editor(user):
    """
    Helper that checks if a user is superuser or in the configured editor groups;
    centralizes the group names in settings.EDITOR_GROUP_NAMES.
    """
    return user.is_superuser or user.groups.filter(
        name__in=getattr(settings, "EDITOR_GROUP_NAMES", ["Editors", "Admins"])
    ).exists()


@rules.predicate
def is_author(user, obj):
    """
    rules predicate: true if the user is authenticated and is the object’s author (compares author_id).
    """
    return user.is_authenticated and getattr(obj, "author_id", None) == user.id


@rules.predicate
def is_editor(user, obj):
    """
    rules predicate: true if the user is authenticated and matches _is_editor; used to gate editorial transitions.
    """
    return user.is_authenticated and _is_editor(user)


"""
(Module-level rules registration)
Adds granular permissions for the editorial workflow 
(submit for review, request rework, publish, archive/restore) 
combining author and editor predicates to prevent self-approval by authors.
"""
# Author/Editor: Draft/Rework/Published → Review
rules.add_perm("content.submit_for_review", is_author | is_editor)

# Editor/Admin: Review → Rework/Published (Autor darf NICHT selbst freigeben)
rules.add_perm("content.request_rework", is_editor & ~is_author)
rules.add_perm("content.publish", is_editor & ~is_author)

# Soft-Delete (Archive)
rules.add_perm("content.archive", is_author | is_editor)

# Restore (from Archive)
rules.add_perm("content.restore", is_author | is_editor)
