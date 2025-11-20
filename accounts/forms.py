from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class UserAccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]  # optional: "email"
        widgets = {
            "first_name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Vorname",
            }),
            "last_name": forms.TextInput(attrs={
                "class": "input input-bordered w-full",
                "placeholder": "Nachname",
            }),
        }
        labels = {
            "first_name": "Vorname",
            "last_name": "Nachname",
        }
