"""Viste compatibili per ordini di lavoro e interventi."""

from fleet import views as fleet_views
from django.contrib.auth.decorators import login_required
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from workshops.models import Membership
from .models import LaborArticle


def work_order_list(request):
    return fleet_views.workflow_list(request, "orders")


def work_order_create(request):
    return fleet_views.workflow_create(request, "orders")


def work_order_detail(request, pk):
    return fleet_views.work_order_detail(request, pk)


def work_order_status(request, pk):
    return fleet_views.workflow_status_action(request, "orders", pk)


def work_order_report(request, pk):
    return fleet_views.work_order_report(request, pk)


def job_list(request):
    return fleet_views.workflow_list(request, "jobs")


def job_create(request):
    return fleet_views.workflow_create(request, "jobs")


def job_action(request, pk, action):
    return fleet_views.job_action(request, pk, action)


def my_jobs(request):
    return fleet_views.my_jobs(request)


def _catalog_context(request):
    membership = Membership.objects.filter(user=request.user, is_active=True, workshop__is_active=True).select_related("workshop").first()
    return membership.workshop if membership else None


@login_required
def labor_article_list(request):
    workshop = _catalog_context(request)
    articles = LaborArticle.objects.filter(workshop=workshop) if workshop else LaborArticle.objects.none()
    return render(request, "orders/labor_article_list.html", {"articles": articles, "has_workshop": workshop is not None})


@login_required
def labor_article_form(request, pk=None):
    if getattr(request.user, "department", "") == "technician":
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Solo il personale d'ufficio può gestire il listino.")
    workshop = _catalog_context(request)
    if workshop is None:
        return redirect("home")
    article = get_object_or_404(LaborArticle, pk=pk, workshop=workshop) if pk else None
    Form = modelform_factory(LaborArticle, exclude=("workshop",))
    form = Form(request.POST or None, instance=article)
    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.workshop = workshop
        article.save()
        return redirect("labor_articles")
    return render(request, "orders/labor_article_form.html", {"form": form, "article": article})


def my_jobs(request):
    return fleet_views.my_jobs(request)
