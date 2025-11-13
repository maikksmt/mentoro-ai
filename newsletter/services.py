from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.signing import TimestampSigner
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Subscriber


def build_unsubscribe_url(subscriber: Subscriber, request) -> str:
    signer = TimestampSigner()
    payload = {"email": subscriber.email}
    token = signer.sign_object(payload)
    return request.build_absolute_uri(reverse("newsletter:unsubscribe_confirm", args=[token]))


def send_double_opt_in_email(subscriber: Subscriber, request) -> None:
    token = subscriber.refresh_doi_token()
    confirmation_url = request.build_absolute_uri(
        reverse("newsletter:confirm", args=[token])
    )
    unsubscribe_url = build_unsubscribe_url(subscriber, request)
    context = {
        "subscriber": subscriber,
        "confirmation_url": confirmation_url,
        "unsubscribe_url": unsubscribe_url,
    }
    subject = render_to_string("newsletter/emails/confirm_subject.txt", context).strip()
    text_body = render_to_string("newsletter/emails/confirm_body.txt", context)
    html_body = render_to_string("newsletter/emails/confirm_body.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[subscriber.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send()
