from django.contrib.auth.models import Group
from django.test import TestCase


class EditorialGroupsTests(TestCase):
    def test_groups_created(self):
        for group_name in ("Admin", "Editor", "Author"):
            with self.subTest(group=group_name):
                self.assertTrue(Group.objects.filter(name=group_name).exists())

    def test_author_group_has_no_delete_permissions(self):
        author_group = Group.objects.get(name="Author")
        self.assertFalse(
            author_group.permissions.filter(codename__startswith="delete_").exists()
        )

    def test_editor_group_can_delete_content(self):
        editor_group = Group.objects.get(name="Editor")
        self.assertTrue(
            editor_group.permissions.filter(
                codename__startswith="delete_",
                content_type__app_label__in=(
                    "content",
                    "guides",
                    "articles",
                ),
            ).exists()
        )

    def test_admin_group_has_global_permission_scope(self):
        admin_group = Group.objects.get(name="Admin")
        self.assertTrue(admin_group.permissions.filter(codename="delete_user").exists())
