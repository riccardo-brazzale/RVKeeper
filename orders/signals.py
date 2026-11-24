from django.db.models.signals import post_save
from django.dispatch import receiver

from workshops.models import Workshop


@receiver(post_save, sender=Workshop)
def create_workshop_price_lists(sender, instance, created, **kwargs):
    if not created:
        return

    from .models import PriceList
    from .pricing import ensure_workshop_price_list

    default_list = PriceList.objects.create(
        workshop=instance,
        code="CLIENTE",
        name="Listino Cliente",
        is_default=True,
    )
    ensure_workshop_price_list(instance)
