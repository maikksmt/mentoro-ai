from django.contrib import messages
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.urls import reverse_lazy
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView

from .forms import SubscriptionForm, UnsubscribeForm
from .models import Subscriber
from .services import send_double_opt_in_email


class SubscribeView(FormView):
    form_class = SubscriptionForm
    template_name = "newsletter/subscribe.html"
    success_url = reverse_lazy("newsletter:subscribe")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("seo_title", _("Newsletter"))
        context.setdefault(
            "seo_description",
            _("Subscribe to the MentoroAI newsletter: updates on tools, comparisons, and guides."),
        )
        return context

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        subscriber, created = Subscriber.objects.get_or_create(email=email)
        if subscriber.unsubscribed_at:
            subscriber.unsubscribed_at = None
            subscriber.unsubscribed_reason = ""
            subscriber.save(update_fields=["unsubscribed_at", "unsubscribed_reason"])

        if not subscriber.is_subscribed:
            send_double_opt_in_email(subscriber, self.request)
            messages.info(self.request, gettext("Please check your inbox to confirm your subscription."))
        else:
            messages.success(self.request, gettext("You are already subscribed."))
        return super().form_valid(form)


class ConfirmSubscriptionView(TemplateView):
    template_name_success = "newsletter/confirm_success.html"
    template_name_error = "newsletter/confirm_error.html"

    def get_template_names(self):
        return [self.template_name_error] if getattr(self, "confirmation_failed", False) else [
            self.template_name_success]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["seo_title"] = _("Confirm newsletter subscription")
        return ctx

    def get(self, request, *args, **kwargs):
        token = kwargs.get("token")
        try:
            subscriber = Subscriber.objects.get(doi_token=token)
        except Subscriber.DoesNotExist:
            self.confirmation_failed = True
            context = self.get_context_data(success=False)
            context["message"] = _("This confirmation link is invalid or has already been used.")
            return self.render_to_response(context, status=404)

        subscriber.mark_confirmed()
        context = self.get_context_data(success=True, email=subscriber.email)
        return self.render_to_response(context)


class UnsubscribeView(FormView):
    form_class = UnsubscribeForm
    template_name = "newsletter/unsubscribe.html"
    success_url = reverse_lazy("newsletter:unsubscribe_done")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        reason = form.cleaned_data.get("reason", "")
        try:
            subscriber = Subscriber.objects.get(email=email, double_opt_in=True)
        except Subscriber.DoesNotExist:
            messages.error(self.request, gettext("No active subscription found for this email."))
            return super().form_valid(form)

        if subscriber.unsubscribed_at:
            messages.info(self.request, gettext("This email is already unsubscribed."))
            return super().form_valid(form)

        subscriber.mark_unsubscribed(reason=reason)
        messages.success(self.request, gettext("You have been unsubscribed."))
        return super().form_valid(form)


# NEW – 1-Klick-Abmeldung über signierten Token
class UnsubscribeConfirmView(TemplateView):
    template_name = "newsletter/unsubscribe_confirm.html"

    def get(self, request, *args, **kwargs):
        token = kwargs.get("token")
        signer = TimestampSigner()
        try:
            payload = signer.unsign_object(token, max_age=60 * 60 * 24 * 30)  # 30 Tage gültig
            email = payload.get("email")
            subscriber = Subscriber.objects.get(email=email, double_opt_in=True)
            if not subscriber.unsubscribed_at:
                subscriber.mark_unsubscribed(reason="link")
            context = {"email": subscriber.email, "already": False}
        except (BadSignature, SignatureExpired, Subscriber.DoesNotExist):
            context = {"email": None, "already": None, "invalid": True}
            return self.render_to_response(context, status=400)

        return self.render_to_response(context)


class UnsubscribeDoneView(TemplateView):
    template_name = "newsletter/unsubscribe_success.html"
