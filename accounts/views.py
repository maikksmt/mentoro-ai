# accounts/views.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from .forms import UserAccountForm  # deine Form: first_name / last_name :contentReference[oaicite:0]{index=0}


class AccountDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "account/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_account_form"] = UserAccountForm(instance=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form = UserAccountForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Your profile has been updated."))
            return redirect("account_dashboard")

        # Form mit Fehlern erneut anzeigen
        context = self.get_context_data()
        context["user_account_form"] = form
        return self.render_to_response(context)
