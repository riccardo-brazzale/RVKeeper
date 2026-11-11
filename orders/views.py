"""Viste compatibili per ordini di lavoro e interventi."""

from fleet import views as fleet_views


def work_order_list(request):
    return fleet_views.workflow_list(request, "orders")


def work_order_create(request):
    return fleet_views.workflow_create(request, "orders")


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
