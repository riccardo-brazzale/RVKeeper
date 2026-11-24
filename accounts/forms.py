
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from .models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "preferred_language",
            "profile",
        )


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class LanguagePreferenceForm(forms.ModelForm):
    preferred_language = forms.ChoiceField(
        choices=[("", _("Use browser language"))] + [
            choice
            for choice in User.LANGUAGE_CHOICES
            if choice[0]
        ],
        required=False,
    )

    class Meta:
        model = User
        fields = ("preferred_language",)


class UsernameEmailPasswordResetForm(PasswordResetForm):
    username = forms.CharField(label=_("Username"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = _("Email address")
        self.order_fields(("username", "email"))

    def get_users(self, email):
        user_model = get_user_model()
        username = self.cleaned_data["username"].strip()
        users = user_model._default_manager.filter(
            username=username,
            email__iexact=email,
            is_active=True,
        )
        for user in users:
            if user.has_usable_password():
                yield user
