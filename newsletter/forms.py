from django import forms
from django.utils.translation import gettext_lazy as _


class SubscriptionForm(forms.Form):
    email = forms.EmailField(
        label=_("email"),
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "class": "input input-bordered w-full",
                "placeholder": "name@example.com",
            }
        ),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class UnsubscribeForm(forms.Form):
    email = forms.EmailField(
        label=_("email"),
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "class": "input input-bordered w-full",
                "placeholder": "name@example.com",
            }
        ),
    )
    reason = forms.CharField(
        label=_("Reason (optional)"),
        required=False,
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full"}),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
