from django.test import TestCase

from clientandsuppliers.models import CamperOwner
from orders.models import WorkOrder
from workshops.models import Workshop

from .forms import WorkOrderForm
from .models import Camper


class WorkOrderFormTests(TestCase):
    def setUp(self):
        self.workshop = Workshop.objects.create(name="Test workshop", slug="test-workshop")
        self.customer = CamperOwner.objects.create(
            workshop=self.workshop,
            kind="customer",
            first_name="Ada",
            last_name="Lovelace",
        )
        self.camper = Camper.objects.create(
            workshop=self.workshop,
            owner=self.customer,
            internal_number="CAMP-001",
            plate="TEST-001",
        )

    def test_work_order_uses_the_selected_campers_owner(self):
        Camper.objects.create(
            workshop=self.workshop,
            owner=self.customer,
            internal_number="CAMP-002",
            plate="TEST-002",
        )
        form = WorkOrderForm(
            {
                "ro_number": "RO-2026-0001",
                "vehicle": str(self.camper.pk),
                "work_classification": "customer_pay",
                "warranty_status": "not_applicable",
            },
            workshop=self.workshop,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("customer", form.fields)
        self.assertEqual(self.customer.campers.count(), 2)

        order = form.save(commit=False)
        self.assertIsInstance(order, WorkOrder)
        self.assertEqual(order.vehicle, self.camper)
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.customer_name, str(self.customer))
        self.assertEqual(form.fields["vehicle"].queryset.count(), 2)

    def test_work_order_requires_a_camper(self):
        form = WorkOrderForm(
            {
                "ro_number": "RO-2026-0002",
                "work_classification": "customer_pay",
                "warranty_status": "not_applicable",
            },
            workshop=self.workshop,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("vehicle", form.errors)
