from django import forms
from django.apps import apps

MODEL_NAMES = [
    ("guide", "Guide"),
    ("usecase", "UseCase"),
    ("prompt", "Prompt"),
]

APP_ORDER = ["guides", "usecases", "prompts", "content"]


def get_model_or_none(name):
    for app_label in APP_ORDER:
        try:
            return apps.get_model(app_label, name)
        except LookupError:
            continue
    return None


class SubmitToReviewForm(forms.Form):
    model = forms.ChoiceField(
        choices=[(n, label) for n, label in MODEL_NAMES if get_model_or_none(label)]
    )
    object_id = forms.IntegerField(min_value=1)


class ReviewUpdateForm(forms.Form):
    model = forms.ChoiceField(
        choices=[(n, label) for n, label in MODEL_NAMES if get_model_or_none(label)]
    )
    object_id = forms.IntegerField(min_value=1)
    status = forms.ChoiceField(
        choices=[
            ("draft", "Draft"),
            ("review", "In Review"),
            ("published", "Published"),
        ]
    )
