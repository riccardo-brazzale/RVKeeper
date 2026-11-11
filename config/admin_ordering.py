from types import MethodType

from django.contrib import admin


APP_ORDER = {
    "workshops": 0,
    "accounts": 1,
    "clientandsuppliers": 2,
    "fleet": 3,
    "orders": 4,
    "parts": 5,
    "quotes": 6,
}

MODEL_ORDER = {
    ("workshops", "workshop"): 0,
    ("workshops", "role"): 1,
    ("workshops", "membership"): 2,
    ("accounts", "user"): 0,
    ("fleet", "auditlog"): 0,
}


def ordered_admin_app_list(site, request, app_label=None):
    app_dict = site._build_app_dict(request, app_label)
    app_list = list(app_dict.values())

    for app in app_list:
        app["models"].sort(
            key=lambda model: MODEL_ORDER.get(
                (app["app_label"], model["object_name"].lower()),
                99,
            )
        )

    app_list.sort(key=lambda app: APP_ORDER.get(app["app_label"], 99))
    return app_list


admin.site.get_app_list = MethodType(ordered_admin_app_list, admin.site)
