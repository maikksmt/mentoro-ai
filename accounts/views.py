from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from .forms import UserAccountForm


@method_decorator(login_required, name="dispatch")
class AccountDashboardView(TemplateView):
    template_name = "account/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["user_form"] = UserAccountForm(instance=user)

        # allauth-URLs für Account-Management
        ctx["email_url"] = reverse("account_email")
        ctx["change_password_url"] = reverse("account_change_password")
        ctx["social_connections_url"] = reverse("socialaccount_connections")
        return ctx

    def post(self, request, *args, **kwargs):
        user = request.user
        form = UserAccountForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            # Optional: Success-Meldung über messages-Framework
            return redirect("account_dashboard")

        ctx = self.get_context_data()
        ctx["user_form"] = form
        return self.render_to_response(ctx)
