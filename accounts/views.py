from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LanguagePreferenceForm


@login_required
def preferences(request):
    form = LanguagePreferenceForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Language preference updated."))
        next_url = request.POST.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect("user_preferences")
    return render(request, "accounts/preferences.html", {"form": form})
