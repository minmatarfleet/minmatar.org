"""Forms for industry admin."""

from django import forms

from industry.helpers.lp_ledger import (
    LpLedgerError,
    account_balance,
    post_ledger_entry,
)
from industry.helpers.public_short_code import (
    is_valid_public_short_code,
    pick_unique_public_short_code_among_actives,
    public_short_code_taken_by_active,
)
from industry.models import (
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointLedgerEntry,
    IndustryOrder,
)


class IndustryOrderAdminForm(forms.ModelForm):
    """Show ``public_short_code`` as read-only; validated in ``clean_public_short_code``."""

    class Meta:
        model = IndustryOrder
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["public_short_code"]
        field.widget.attrs["readonly"] = True
        field.required = False
        inst = self.instance
        if inst.pk and inst.public_short_code:
            field.initial = inst.public_short_code
        elif not inst.pk:
            field.initial = pick_unique_public_short_code_among_actives()

    def clean_public_short_code(self):
        raw = (self.data.get("public_short_code") or "").strip()
        if self.instance.pk:
            return self.instance.public_short_code
        if is_valid_public_short_code(
            raw
        ) and not public_short_code_taken_by_active(
            raw, exclude_order_pk=None
        ):
            return raw
        return pick_unique_public_short_code_among_actives()


class IndustryLoyaltyPointAccountAdminForm(forms.ModelForm):
    """
    Account edit form with an explicit credit/debit poster.

    Leave the ledger fields blank to save account/contact changes only.
    """

    class Meta:
        model = IndustryLoyaltyPointAccount
        fields = "__all__"

    LEDGER_CREDIT = "credit"
    LEDGER_DEBIT = "debit"
    LEDGER_DIRECTION_CHOICES = (
        (LEDGER_CREDIT, "Credit (LP in)"),
        (LEDGER_DEBIT, "Debit (LP out)"),
    )

    ledger_direction = forms.ChoiceField(
        choices=LEDGER_DIRECTION_CHOICES,
        required=False,
        initial=LEDGER_CREDIT,
        label="Direction",
        help_text="Optional. Fill quantity below to post one credit or debit on save.",
    )
    ledger_quantity = forms.IntegerField(
        required=False,
        min_value=1,
        label="LP quantity",
        help_text="Positive LP amount to credit or debit. Leave blank to skip.",
    )
    ledger_isk_per_lp = forms.IntegerField(
        required=False,
        min_value=1,
        label="ISK per LP (this lot)",
        help_text=(
            "Price for this intake/draw only (e.g. 825 or 850). "
            "Defaults to the account offer or currency default when blank."
        ),
    )
    ledger_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Ledger notes",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        offer = None
        inst = self.instance
        if inst and inst.pk:
            if inst.isk_per_lp:
                offer = inst.isk_per_lp
            elif inst.loyalty_point_id:
                offer = inst.loyalty_point.default_isk_per_lp
        if offer:
            self.fields["ledger_isk_per_lp"].initial = offer

    def clean(self):
        cleaned = super().clean()
        quantity = cleaned.get("ledger_quantity")
        direction = cleaned.get("ledger_direction") or self.LEDGER_CREDIT
        isk_per_lp = cleaned.get("ledger_isk_per_lp")
        if quantity is None:
            return cleaned
        if not direction:
            self.add_error(
                "ledger_direction",
                "Choose credit or debit when posting a quantity.",
            )
        if isk_per_lp is None:
            inst = self.instance
            if inst and inst.isk_per_lp:
                isk_per_lp = inst.isk_per_lp
            elif inst and inst.loyalty_point_id:
                isk_per_lp = inst.loyalty_point.default_isk_per_lp
            cleaned["ledger_isk_per_lp"] = isk_per_lp
        if cleaned.get("ledger_isk_per_lp") is None:
            self.add_error(
                "ledger_isk_per_lp",
                "Enter ISK/LP for this lot (or set an account/currency default).",
            )
        if (
            direction == self.LEDGER_DEBIT
            and self.instance
            and self.instance.pk
            and not self.errors
        ):
            balance = account_balance(self.instance)
            if quantity > balance:
                self.add_error(
                    "ledger_quantity",
                    f"Insufficient LP balance: have {balance:,}, debit {quantity:,}.",
                )
        return cleaned

    def post_ledger_if_requested(self, *, user=None):
        """Post the optional ledger row after the account is saved. Returns entry or None."""
        quantity = self.cleaned_data.get("ledger_quantity")
        if quantity is None:
            return None
        direction = (
            self.cleaned_data.get("ledger_direction") or self.LEDGER_CREDIT
        )
        amount = int(quantity)
        if direction == self.LEDGER_DEBIT:
            amount = -amount
        try:
            return post_ledger_entry(
                self.instance,
                amount,
                int(self.cleaned_data["ledger_isk_per_lp"]),
                notes=self.cleaned_data.get("ledger_notes") or "",
                user=user,
            )
        except LpLedgerError as exc:
            raise forms.ValidationError(str(exc)) from exc


class IndustryLoyaltyPointLedgerEntryAdminForm(forms.ModelForm):
    """Add ledger rows via the standalone ledger admin using credit/debit fields."""

    class Meta:
        model = IndustryLoyaltyPointLedgerEntry
        fields = ("account", "notes")

    direction = forms.ChoiceField(
        choices=IndustryLoyaltyPointAccountAdminForm.LEDGER_DIRECTION_CHOICES,
        initial=IndustryLoyaltyPointAccountAdminForm.LEDGER_CREDIT,
        label="Direction",
    )
    quantity = forms.IntegerField(min_value=1, label="LP quantity")
    isk_per_lp = forms.IntegerField(min_value=1, label="ISK per LP")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # On change, admin fieldsets/readonly drop these; the model
            # isk_per_lp is shown via readonly_fields instead.
            for name in ("direction", "quantity", "isk_per_lp"):
                self.fields.pop(name, None)

    def save(self, commit=True):
        if self.instance.pk:
            return self._save_existing(commit)
        return self._save_new(commit)

    def _save_existing(self, commit: bool):
        existing = self.instance
        existing.notes = self.cleaned_data.get("notes") or ""
        if commit:
            existing.save(update_fields=["notes"])
        else:
            # Admin always uses commit=False then form.save_m2m().
            self.save_m2m = self._save_m2m_noop
        return existing

    def _save_new(self, commit: bool):
        direction = self.cleaned_data["direction"]
        quantity = int(self.cleaned_data["quantity"])
        amount = (
            -quantity
            if direction == IndustryLoyaltyPointAccountAdminForm.LEDGER_DEBIT
            else quantity
        )
        self.instance = post_ledger_entry(
            self.cleaned_data["account"],
            amount,
            int(self.cleaned_data["isk_per_lp"]),
            notes=self.cleaned_data.get("notes") or "",
            user=getattr(self, "_request_user", None),
        )
        if not commit:
            self.save_m2m = self._save_m2m_noop
        return self.instance

    @staticmethod
    def _save_m2m_noop():
        """No M2M fields; satisfy ModelAdmin.save_related after commit=False."""
        return None
