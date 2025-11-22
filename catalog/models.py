# catalog/models.py
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from parler.managers import TranslatableManager
from parler.models import TranslatableModel, TranslatedFields
from parler.utils.context import switch_language
from taggit.managers import TaggableManager


class Category(TranslatableModel):
    translations = TranslatedFields(
        name=models.CharField(max_length=120),
        slug=models.SlugField(_("Slug"), max_length=220, unique=True),
        description=models.TextField(blank=True),
    )
    objects = TranslatableManager()

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")

    def __str__(self):
        return self.safe_translation_getter("name", any_language=True) or f"Category #{self.pk}"


PRICING_MODEL_CHOICES = [
    ("free", _("Completely free")),
    ("freemium", _("Freemium (free basic, paid pro)")),
    ("subscription", _("Subscription (monthly/yearly)")),
    ("payg", _("Pay-as-you-go / usage-based")),
    ("license", _("One-time license / lifetime deal")),
    ("opensource", _("Open-source / self-hosted")),
    ("custom", _("Contact sales / custom pricing")),
    ("other", _("Other / mixed model")),
]


class Tool(TranslatableModel):
    vendor = models.CharField(max_length=150, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="logos/", blank=True, null=True)
    language_support = models.JSONField(default=list)
    pricing_model = models.CharField(
        max_length=32,
        choices=PRICING_MODEL_CHOICES,
        blank=True,
    )
    free_tier = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    categories = models.ManyToManyField(Category, related_name="tools", blank=True)
    tags = TaggableManager(blank=True)
    translations = TranslatedFields(
        name=models.CharField(max_length=250),
        slug=models.SlugField(_("Slug"), max_length=220, unique=True),
        short_description=models.TextField(blank=True),
        long_description=models.TextField(blank=True),
    )
    objects = TranslatableManager()
    ordering = ["id"]

    class Meta:
        verbose_name = "Tool"
        verbose_name_plural = "Tools"
        ordering = ("-updated_at", "-pk")

    def __str__(self):
        return self.safe_translation_getter("name", any_language=True) or f"Tool #{self.pk}"

    def get_absolute_url(self, language: str | None = None):
        lang = language or get_language()
        with switch_language(self, lang):
            slug = self.safe_translation_getter("slug")
        return reverse("catalog:detail", kwargs={"slug": slug})


class PricingTier(TranslatableModel):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="pricing", )
    translations = TranslatedFields(
        name=models.CharField(max_length=250),
        price_month=models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, ),
        price_year=models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, ),
        features=models.JSONField(default=list, blank=True),
    )
    objects = TranslatableManager()

    class Meta:
        verbose_name = _("Pricing tier")
        verbose_name_plural = _("Pricing tiers")

    def __str__(self):
        return f"{self.tool} – {self.safe_translation_getter('name', any_language=True)}"


class AffiliateProgram(models.Model):
    COMMISSION_CHOICES = [
        ("flat", _("Flat")),
        ("percent", _("% of sales")),
        ("recurring", _("Recurring")),
    ]
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="affiliates")
    network = models.CharField(max_length=250, blank=True)
    program_url = models.URLField(blank=True)
    commission_type = models.CharField(
        max_length=30, choices=COMMISSION_CHOICES, default="percent"
    )
    commission_value = models.CharField(
        max_length=30, blank=True
    )  # i.e. "30%" oder "€50"
    cookie_days = models.IntegerField(default=30)
    tracking_note = models.CharField(max_length=250, blank=True)

    class Meta:
        verbose_name = _("Affiliate-Program")
        verbose_name_plural = _("Affiliate-Programs")

    def __str__(self):
        return f"Affiliate: {self.tool}"
