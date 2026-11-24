from decimal import Decimal
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from clientandsuppliers.models import CamperOwner
from fleet.management.commands.populate_demo_data import generated_parts
from orders.models import (
    BillOfMaterials,
    BillOfMaterialsLine,
    CustomerItemDiscount,
    Job,
    JobParticipation,
    LaborArticle,
    Notification,
    PauseReason,
    PriceList,
    PriceListItem,
    TimeEvent,
    WorkOrder,
)
from orders.pricing import ensure_workshop_price_list, resolve_item_price, rotate_price_list_prices
from parts.forms import PartForm
from parts.models import (
    JobPartUsage,
    Part,
    PartMovement,
    PartsRequest,
    TransferSlipLine,
    WarehouseNote,
    WarehouseNoteRead,
)
from quotes.models import QuoteLine
from quotes.views import _apply_line_pricing
from workshops.models import Membership, Workshop

from .forms import CamperForm, WorkOrderForm
from .models import Camper


class PopulateDemoDataCommandTests(TestCase):
    def setUp(self):
        self.workshop = Workshop.objects.create(
            name="Demo workshop",
            slug="populate-demo-workshop",
            country="US",
        )

    def _run_command(self):
        call_command(
            "populate_demo_data",
            workshop=self.workshop.slug,
            stdout=StringIO(),
        )

    def test_command_prepares_customer_exceptions_without_assigning_them(self):
        self._run_command()

        customers = CamperOwner.objects.filter(
            workshop=self.workshop,
            kind__in=("customer", "both"),
        )
        self.assertFalse(customers.exclude(price_list__is_default=True).exists())
        exception_lists = PriceList.objects.filter(
            workshop=self.workshop,
            customer__isnull=False,
        )
        self.assertEqual(exception_lists.count(), 3)
        self.assertEqual(CustomerItemDiscount.objects.filter(customer__in=customers).count(), 9)
        workshop_list = PriceList.objects.get(workshop=self.workshop, is_workshop=True)
        self.assertFalse(PriceListItem.objects.filter(price_list=workshop_list).exists())
        self.assertEqual(workshop_list.code, "OFFICINE")
        self.assertEqual(
            PriceList.objects.get(workshop=self.workshop, is_default=True).code,
            "CLIENTE",
        )

    def test_command_populates_requested_counts_and_is_idempotent(self):
        self._run_command()

        self.assertEqual(
            CamperOwner.objects.filter(
                workshop=self.workshop,
                kind__in=("customer", "both"),
            ).count(),
            100,
        )
        self.assertEqual(Part.objects.filter(workshop=self.workshop).count(), 1000)
        self.assertEqual(WorkOrder.objects.filter(workshop=self.workshop).count(), 10)
        self.assertEqual(Job.objects.filter(workshop=self.workshop).count(), 30)
        self.assertEqual(PartsRequest.objects.filter(workshop=self.workshop).count(), 20)
        self.assertEqual(
            WorkOrder.objects.filter(workshop=self.workshop, status="completed").count(),
            3,
        )
        self.assertEqual(
            PartsRequest.objects.filter(workshop=self.workshop, status="delivered").count(),
            13,
        )
        self.assertEqual(
            PartsRequest.objects.filter(workshop=self.workshop, status="pending").count(),
            7,
        )
        self.assertEqual(PartMovement.objects.filter(workshop=self.workshop).count(), 13)
        demo_customer = CamperOwner.objects.filter(
            workshop=self.workshop, email__endswith="@contacts.example",
        ).order_by("email").first()
        self.assertIsNotNone(demo_customer)
        original_demo_notes = demo_customer.notes
        self.assertTrue(original_demo_notes)
        demo_number, demo_name, demo_description, _, _, demo_price_value, *_ = next(generated_parts())
        demo_part = Part.objects.get(workshop=self.workshop, part_number=demo_number)
        demo_price = PriceListItem.objects.get(
            price_list__workshop=self.workshop,
            price_list__is_default=True,
            part=demo_part,
        )
        self.assertEqual(demo_price.unit_price, Decimal(demo_price_value))
        self.assertEqual(demo_part.description, demo_description)
        stock_before_rerun = dict(
            Part.objects.filter(workshop=self.workshop).values_list("pk", "quantity")
        )

        demo_customer.notes = "Old demo note"
        demo_customer.save(update_fields=("notes",))
        demo_part.name = "Old demo name"
        demo_part.save(update_fields=("name",))
        demo_price.unit_price = Decimal("999.99")
        demo_price.save(update_fields=("unit_price",))
        self._run_command()

        demo_customer.refresh_from_db()
        demo_part.refresh_from_db()
        demo_price.refresh_from_db()
        self.assertEqual(demo_customer.notes, original_demo_notes)
        self.assertEqual(demo_part.name, demo_name)
        self.assertEqual(demo_price.unit_price, Decimal(demo_price_value))
        self.assertEqual(Part.objects.filter(workshop=self.workshop).count(), 1000)
        self.assertEqual(WorkOrder.objects.filter(workshop=self.workshop).count(), 10)
        self.assertEqual(Job.objects.filter(workshop=self.workshop).count(), 30)
        self.assertEqual(PartsRequest.objects.filter(workshop=self.workshop).count(), 20)
        self.assertEqual(PartMovement.objects.filter(workshop=self.workshop).count(), 13)
        self.assertEqual(
            dict(Part.objects.filter(workshop=self.workshop).values_list("pk", "quantity")),
            stock_before_rerun,
        )


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
                "tariff_type": "standard",
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
        self.assertIn(self.customer.customer_code, str(form["vehicle"]))

    def test_customer_code_is_shown_when_selecting_a_contact_for_a_camper(self):
        self.assertEqual(self.customer.customer_code, f"CLI-{self.customer.pk:06d}")
        form = CamperForm(workshop=self.workshop)

        self.assertIn(self.customer.customer_code, str(form["owner"]))

    def test_bom_expands_seven_jobs_in_work_order(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="bom-admin",
            email="bom-admin@example.com",
            password="test-password",
            profile="admin",
        )
        Membership.objects.create(user=user, workshop=self.workshop, is_active=True)
        bom = BillOfMaterials.objects.create(
            workshop=self.workshop,
            code="BOM-TEST",
            name="Controllo completo",
        )
        for sequence in range(1, 8):
            BillOfMaterialsLine.objects.create(
                bom=bom,
                sequence=sequence,
                title=f"Sotto-attività {sequence}",
                department="technician",
                specialty="general",
            )
        self.client.force_login(user)
        response = self.client.post(
            reverse("fleet:workflow_create", kwargs={"module": "orders"}),
            {
                "vehicle": str(self.camper.pk),
                "bom_template": str(bom.pk),
                "work_classification": "customer_pay",
                "warranty_status": "not_applicable",
                "reception_notes": "",
                "checklist": "",
                "damages": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = WorkOrder.objects.get(workshop=self.workshop)
        self.assertEqual(order.jobs.count(), 7)
        self.assertEqual(
            list(order.jobs.order_by("job_number").values_list("title", flat=True)),
            [f"Sotto-attività {sequence}" for sequence in range(1, 8)],
        )

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


class TimeReportTests(TestCase):
    def setUp(self):
        self.workshop = Workshop.objects.create(name="Report workshop", slug="report-workshop")
        user_model = get_user_model()
        self.office_user = user_model.objects.create_user(
            "report-office", "report-office@example.test", "password", profile="admin"
        )
        self.technician = user_model.objects.create_user(
            "report-tech", "report-tech@example.test", "password", profile="mechanic"
        )
        self.other_technician = user_model.objects.create_user(
            "report-tech-2", "report-tech-2@example.test", "password", profile="mechanic"
        )
        for user in (self.office_user, self.technician, self.other_technician):
            Membership.objects.create(user=user, workshop=self.workshop)
        self.work_order = WorkOrder.objects.create(
            workshop=self.workshop,
            ro_number="RO-REPORT-001",
        )
        self.job = Job.objects.create(
            workshop=self.workshop,
            work_order=self.work_order,
            title="Replace water pump",
            job_number=1,
        )
        self.client.force_login(self.office_user)

    def _create_event(self, mechanic, event_type, day, hour, minute=0):
        event_at = timezone.make_aware(datetime(2026, 3, day, hour, minute))
        return TimeEvent.objects.create(
            workshop=self.workshop,
            job=self.job,
            mechanic=mechanic,
            event_type=event_type,
            event_at=event_at,
        )

    def test_report_filters_by_technician_and_clips_sessions_to_period(self):
        self._create_event(self.technician, "start", 9, 23, 30)
        self._create_event(self.technician, "finish", 10, 0, 30)
        self._create_event(self.technician, "start", 10, 9)
        self._create_event(self.technician, "finish", 10, 10)
        self._create_event(self.other_technician, "start", 10, 9)
        self._create_event(self.other_technician, "finish", 10, 11)
        self._create_event(self.technician, "start", 11, 9)
        self._create_event(self.technician, "finish", 11, 11)

        response = self.client.get(reverse("report"), {
            "technician": self.technician.pk,
            "date_from": "2026-03-10",
            "date_to": "2026-03-10",
        })

        self.assertEqual(response.status_code, 200)
        report_data = response.context["report_data"]
        self.assertEqual(len(report_data["rows"]), 2)
        self.assertEqual(report_data["total_minutes"], 90)
        self.assertEqual(report_data["order_totals"][0]["minutes"], 90)
        self.assertEqual(report_data["technician_totals"][0]["technician"], self.technician)

    def test_report_exports_detailed_pdf_and_excel(self):
        self._create_event(self.technician, "start", 10, 9)
        self._create_event(self.technician, "finish", 10, 10)
        filters = {
            "technician": self.technician.pk,
            "date_from": "2026-03-10",
            "date_to": "2026-03-10",
        }

        pdf_response = self.client.get(reverse("report"), {**filters, "export": "pdf"})
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))

        excel_response = self.client.get(reverse("report"), {**filters, "export": "xlsx"})
        self.assertEqual(
            excel_response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        from openpyxl import load_workbook

        workbook = load_workbook(BytesIO(excel_response.content), read_only=True)
        self.assertEqual(workbook.sheetnames, ["Dettaglio", "Totali ordine", "Totali tecnico"])
        self.assertEqual(workbook["Dettaglio"].max_row, 7)
        self.assertEqual(workbook["Dettaglio"]["A7"].value, self.work_order.ro_number)


class JobPartsWorkflowTests(TestCase):
    def setUp(self):
        self.workshop = Workshop.objects.create(name="Parts workshop", slug="parts-workshop")
        user_model = get_user_model()
        self.mechanic = user_model.objects.create_user(
            "mechanic", "mechanic@example.test", "password", profile="mechanic"
        )
        self.parts_user = user_model.objects.create_user(
            "warehouse", "warehouse@example.test", "password", profile="warehouse"
        )
        self.reception_user = user_model.objects.create_user(
            "reception", "reception@example.test", "password", profile="admin"
        )
        Membership.objects.create(user=self.mechanic, workshop=self.workshop)
        self.parts_membership = Membership.objects.create(
            user=self.parts_user, workshop=self.workshop
        )
        Membership.objects.create(user=self.reception_user, workshop=self.workshop)
        self.customer = CamperOwner.objects.create(
            workshop=self.workshop, kind="customer", first_name="Ada", last_name="Lovelace"
        )
        self.camper = Camper.objects.create(
            workshop=self.workshop, owner=self.customer, internal_number="CAMP-PARTS", plate="PARTS-001"
        )
        self.work_order = WorkOrder.objects.create(
            workshop=self.workshop, vehicle=self.camper, customer=self.customer, ro_number="RO-TEST-1"
        )
        self.job = Job.objects.create(
            workshop=self.workshop, work_order=self.work_order, title="Replace filter", job_number=1
        )
        self.part = Part.objects.create(
            workshop=self.workshop, part_number="FILTER-1", name="Oil filter", unit="pz", quantity=10
        )
        self.part2 = Part.objects.create(
            workshop=self.workshop, part_number="SEAL-1", name="Seal", unit="scatola", quantity=4
        )
        self.participation = JobParticipation.objects.create(
            workshop=self.workshop, job=self.job, mechanic=self.mechanic,
            started_at=timezone.now(), is_active=True,
        )
        self.client.force_login(self.mechanic)

    def test_new_customer_is_assigned_to_the_default_price_list(self):
        self.assertIsNotNone(self.customer.price_list_id)
        self.assertTrue(self.customer.price_list.is_default)

    def test_customer_detail_displays_assigned_default_price_list(self):
        self.client.force_login(self.reception_user)

        response = self.client.get(reverse("customer_detail", args=(self.customer.pk,)))

        self.assertContains(response, self.customer.price_list.name)
        self.assertContains(response, "Listino assegnato:")
        self.assertContains(
            response,
            f'href="{reverse("price_list_create")}?customer={self.customer.pk}"',
        )
        price_list_response = self.client.get(
            f'{reverse("price_list_create")}?customer={self.customer.pk}'
        )
        self.assertEqual(price_list_response.status_code, 200)
        self.assertEqual(
            price_list_response.context["form"]["code"].value(),
            self.customer.customer_code,
        )
        self.assertTrue(price_list_response.context["form"].fields["code"].disabled)
        self.assertTrue(price_list_response.context["form"].fields["customer"].disabled)
        discount_prefix = price_list_response.context["discount_formset"].prefix
        save_response = self.client.post(
            f'{reverse("price_list_create")}?customer={self.customer.pk}',
            {
                "name": f"Listino {self.customer}",
                "is_active": "on",
                f"{discount_prefix}-TOTAL_FORMS": "3",
                f"{discount_prefix}-INITIAL_FORMS": "0",
                f"{discount_prefix}-MIN_NUM_FORMS": "0",
                f"{discount_prefix}-MAX_NUM_FORMS": "1000",
                f"{discount_prefix}-0-part": str(self.part.pk),
                f"{discount_prefix}-0-discount_percent": "10.00",
            },
        )
        self.assertRedirects(save_response, reverse("customer_detail", args=(self.customer.pk,)))
        price_list = PriceList.objects.get(workshop=self.workshop, customer=self.customer)
        self.assertEqual(price_list.code, self.customer.customer_code)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.price_list_id, price_list.pk)
        self.assertFalse(PriceListItem.objects.filter(price_list=price_list).exists())
        self.assertEqual(
            CustomerItemDiscount.objects.get(customer=self.customer, part=self.part).discount_percent,
            Decimal("10.00"),
        )

    def test_price_rotation_skips_rows_without_future_price(self):
        price_list = self.customer.price_list
        today = timezone.localdate()
        rotating = PriceListItem.objects.create(
            price_list=price_list, part=self.part,
            unit_price=Decimal("10.00"), valid_from=today,
            future_price=Decimal("12.00"), future_valid_from=today + timedelta(days=30),
        )
        unchanged = PriceListItem.objects.create(
            price_list=price_list, part=self.part2,
            unit_price=Decimal("20.00"), valid_from=today,
        )

        rotated_count, skipped_count = rotate_price_list_prices(price_list)

        self.assertEqual((rotated_count, skipped_count), (1, 1))
        rotating.refresh_from_db()
        unchanged.refresh_from_db()
        self.assertEqual(rotating.previous_price, Decimal("10.00"))
        self.assertEqual(rotating.unit_price, Decimal("12.00"))
        self.assertIsNone(rotating.future_price)
        self.assertEqual(unchanged.unit_price, Decimal("20.00"))
        self.assertIsNone(unchanged.previous_price)

    def test_price_resolution_uses_the_effective_date(self):
        today = timezone.localdate()
        PriceListItem.objects.create(
            price_list=self.customer.price_list,
            part=self.part,
            previous_price=Decimal("80.00"),
            previous_valid_from=today - timedelta(days=30),
            unit_price=Decimal("100.00"),
            valid_from=today,
            future_price=Decimal("120.00"),
            future_valid_from=today + timedelta(days=30),
        )

        before_current = resolve_item_price(
            self.customer, part=self.part, effective_date=today - timedelta(days=1),
        )
        current = resolve_item_price(self.customer, part=self.part, effective_date=today)
        future = resolve_item_price(
            self.customer, part=self.part, effective_date=today + timedelta(days=30),
        )

        self.assertEqual(before_current["unit_price"], Decimal("80.00"))
        self.assertEqual(current["unit_price"], Decimal("100.00"))
        self.assertEqual(future["unit_price"], Decimal("120.00"))

    def test_billing_prices_can_be_proposed_and_overridden_per_line(self):
        today = timezone.localdate()
        list_price = self.customer.price_list
        labor_article = LaborArticle.objects.create(
            workshop=self.workshop, code="LAB-1", description="Labor",
        )
        PriceListItem.objects.create(
            price_list=list_price, part=self.part, unit_price=Decimal("100.00"), valid_from=today,
        )
        PriceListItem.objects.create(
            price_list=list_price, labor_article=labor_article,
            unit_price=Decimal("80.00"), valid_from=today,
        )
        CustomerItemDiscount.objects.create(
            customer=self.customer, part=self.part, discount_percent=Decimal("10.00"),
        )
        CustomerItemDiscount.objects.create(
            customer=self.customer, labor_article=labor_article, discount_percent=Decimal("10.00"),
        )
        self.work_order.status = "completed"
        self.work_order.completed_at = timezone.now()
        self.work_order.save(update_fields=("status", "completed_at"))
        self.job.labor_article = labor_article
        self.job.save(update_fields=("labor_article",))
        request = PartsRequest.objects.create(
            workshop=self.workshop, work_order=self.work_order, job=self.job, part=self.part,
            quantity_requested=Decimal("1"), quantity_delivered=Decimal("1"),
            status="delivered",
        )
        self.client.force_login(self.reception_user)

        response = self.client.get(reverse("work_order_billing", args=(self.work_order.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["parts_formset"].forms[0].proposed_price,
            Decimal("90.00"),
        )
        self.assertEqual(
            response.context["labor_formset"].forms[0].proposed_price,
            Decimal("72.00"),
        )
        post_data = {
            "parts-TOTAL_FORMS": "1",
            "parts-INITIAL_FORMS": "1",
            "parts-MIN_NUM_FORMS": "0",
            "parts-MAX_NUM_FORMS": "1000",
            "parts-0-id": str(request.pk),
            "parts-0-invoice_unit_price_override": "87.50",
            "labor-TOTAL_FORMS": "1",
            "labor-INITIAL_FORMS": "1",
            "labor-MIN_NUM_FORMS": "0",
            "labor-MAX_NUM_FORMS": "1000",
            "labor-0-id": str(self.job.pk),
            "labor-0-invoice_hourly_rate_override": "70.00",
            "usage-TOTAL_FORMS": "0",
            "usage-INITIAL_FORMS": "0",
            "usage-MIN_NUM_FORMS": "0",
            "usage-MAX_NUM_FORMS": "1000",
        }

        save_response = self.client.post(
            reverse("work_order_billing", args=(self.work_order.pk,)), post_data,
        )

        self.assertRedirects(save_response, reverse("work_order_billing", args=(self.work_order.pk,)))
        request.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(request.invoice_unit_price_override, Decimal("87.50"))
        self.assertEqual(self.job.invoice_hourly_rate_override, Decimal("70.00"))
        with patch("orders.views.resolve_item_price") as resolve_price:
            pdf_response = self.client.post(
                reverse("work_order_report", args=(self.work_order.pk,)),
                {"mark_invoiced": "0"},
            )
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        resolve_price.assert_not_called()

    def test_customer_part_discount_is_applied_to_quotes(self):
        PriceListItem.objects.create(
            price_list=self.customer.price_list,
            part=self.part,
            unit_price=Decimal("100.00"),
            valid_from=timezone.localdate(),
        )
        CustomerItemDiscount.objects.create(
            customer=self.customer, part=self.part, discount_percent=Decimal("15.00"),
        )
        line = QuoteLine(part=self.part, unit_price=Decimal("0.00"))

        _apply_line_pricing(line, self.customer)

        self.assertEqual(line.unit_price, Decimal("100.00"))
        self.assertEqual(line.discount_percent, Decimal("15.00"))
        self.assertEqual(line.total, Decimal("85.00"))

    def _request_payload(self, rows):
        prefix = f"parts-{self.job.pk}"
        payload = {
            f"{prefix}-TOTAL_FORMS": str(len(rows)),
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
        for index, row in enumerate(rows):
            payload.update({
                f"{prefix}-{index}-part": row.get("part", ""),
                f"{prefix}-{index}-quantity_requested": row.get("quantity", ""),
                f"{prefix}-{index}-notes": row.get("notes", ""),
            })
        return payload

    def _completion_payload(self, rows=(), confirmed=True):
        prefix = f"used-parts-{self.job.pk}"
        payload = {
            f"{prefix}-TOTAL_FORMS": str(len(rows) or 1),
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
        for index, row in enumerate(rows):
            payload[f"{prefix}-{index}-part"] = row.get("part", "")
            payload[f"{prefix}-{index}-quantity_used"] = row.get("quantity", "")
        if not rows:
            payload[f"{prefix}-0-part"] = ""
            payload[f"{prefix}-0-quantity_used"] = ""
        if confirmed:
            payload["parts_used_confirmed"] = "1"
        return payload

    def test_job_request_creates_multiple_lines_and_notifies_warehouse(self):
        response = self.client.post(
            reverse("job_parts_request", args=(self.job.pk,)),
            self._request_payload([
                {"part": str(self.part.pk), "quantity": "2"},
                {"part": str(self.part2.pk), "quantity": "1"},
            ]),
        )

        self.assertEqual(response.status_code, 302)
        requests = list(PartsRequest.objects.order_by("pk"))
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(item.job_id == self.job.pk for item in requests))
        self.assertTrue(all(item.work_order_id == self.work_order.pk for item in requests))
        self.assertEqual(requests[0].part, self.part)
        self.assertEqual(requests[0].unit, "pz")
        self.assertEqual(requests[1].part, self.part2)
        self.assertEqual(requests[1].unit, "scatola")
        self.assertEqual(
            Notification.objects.filter(user=self.parts_user, work_order=self.work_order).count(), 1
        )

    def test_job_request_falls_back_to_workshop_notification_without_warehouse_users(self):
        self.parts_membership.is_active = False
        self.parts_membership.save(update_fields=("is_active",))
        self.client.post(
            reverse("job_parts_request", args=(self.job.pk,)),
            self._request_payload([{"part": str(self.part.pk), "quantity": "1"}]),
        )

        notification = Notification.objects.get(work_order=self.work_order)
        self.assertIsNone(notification.user_id)

    def test_expensive_part_request_requires_customer_and_reception_approval(self):
        price_list = self.customer.price_list
        PriceListItem.objects.create(price_list=price_list, part=self.part, unit_price=Decimal("150.00"))

        self.client.post(
            reverse("job_parts_request", args=(self.job.pk,)),
            self._request_payload([{"part": str(self.part.pk), "quantity": "1"}]),
        )
        item = PartsRequest.objects.get()
        self.assertEqual(item.approval_status, "awaiting_customer")
        self.assertEqual(item.customer_quoted_price, Decimal("150.00"))
        self.assertTrue(
            Notification.objects.filter(
                user=self.reception_user,
                title="Customer approval required",
                work_order=self.work_order,
            ).exists()
        )

        self.client.force_login(self.parts_user)
        self.client.post(reverse("parts_request_action", args=(item.pk, "prepare")))
        item.refresh_from_db()
        self.assertEqual(item.status, "pending")

        self.client.force_login(self.reception_user)
        self.client.post(reverse("parts_request_action", args=(item.pk, "customer_approved")))
        item.refresh_from_db()
        self.assertEqual(item.approval_status, "pending")
        self.assertEqual(item.customer_approval_recorded_by, self.reception_user)

        self.client.post(reverse("parts_request_action", args=(item.pk, "approve")))
        item.refresh_from_db()
        self.assertEqual(item.approval_status, "approved")

        self.client.force_login(self.parts_user)
        self.client.post(reverse("parts_request_action", args=(item.pk, "prepare")))
        item.refresh_from_db()
        self.assertEqual(item.status, "preparing")

    def test_catalogs_have_no_price_fields_and_unlisted_items_have_no_fallback_price(self):
        self.assertNotIn("sale_price", PartForm(workshop=self.workshop).fields)
        self.assertNotIn("cost_price", PartForm(workshop=self.workshop).fields)
        self.assertNotIn("sale_price", {field.name for field in Part._meta.fields})
        self.assertNotIn("hourly_rate", {field.name for field in LaborArticle._meta.fields})

        pricing = resolve_item_price(self.customer, part=self.part)

        self.assertIsNone(pricing["unit_price"])
        self.assertIsNone(pricing["total_unit_price"])

        self.client.force_login(self.reception_user)
        part_response = self.client.get(reverse("part_create"))
        labor_response = self.client.get(reverse("price_list_edit", args=(self.customer.price_list_id,)))

        self.assertNotIn("sale_price", part_response.context["form"].fields)
        self.assertNotIn("cost_price", part_response.context["form"].fields)
        self.assertContains(labor_response, "Testata listino")
        self.assertNotContains(labor_response, "Labor articles")
        self.assertEqual(self.client.get("/ordini/articoli-manodopera/").status_code, 404)

    def test_customer_price_resolution_uses_workshop_then_default_fallback(self):
        default_list = self.customer.price_list
        default_list.future_valid_from = timezone.localdate() + timedelta(days=30)
        default_list.save(update_fields=("future_valid_from",))
        PriceListItem.objects.create(price_list=default_list, part=self.part, unit_price=Decimal("100.00"))
        PriceListItem.objects.create(price_list=default_list, part=self.part2, unit_price=Decimal("50.00"))
        workshop_list = ensure_workshop_price_list(self.workshop)
        PriceListItem.objects.create(price_list=workshop_list, part=self.part2, unit_price=Decimal("40.00"))
        self.assertEqual(resolve_item_price(self.customer, part=self.part)["unit_price"], Decimal("100.00"))
        customer_list = PriceList.objects.create(
            workshop=self.workshop,
            code=self.customer.customer_code,
            name="Eccezioni Ada",
            customer=self.customer,
        )
        self.customer.price_list = customer_list
        self.customer.save(update_fields=("price_list",))

        CustomerItemDiscount.objects.create(
            customer=self.customer, part=self.part, discount_percent=Decimal("15.00"),
        )
        self.assertEqual(resolve_item_price(self.customer, part=self.part)["unit_price"], Decimal("100.00"))
        self.assertEqual(resolve_item_price(self.customer, part=self.part)["total_unit_price"], Decimal("85.00"))
        self.assertEqual(resolve_item_price(self.customer, part=self.part2)["unit_price"], Decimal("40.00"))
        default_item = PriceListItem.objects.get(price_list=default_list, part=self.part)
        default_item.unit_price = Decimal("200.00")
        default_item.save(update_fields=("unit_price",))
        self.assertEqual(resolve_item_price(self.customer, part=self.part)["total_unit_price"], Decimal("170.00"))

    def test_labor_code_can_be_created_from_default_price_list(self):
        self.client.force_login(self.reception_user)
        default_list = self.customer.price_list
        default_list.current_valid_from = timezone.localdate()
        default_list.future_valid_from = timezone.localdate() + timedelta(days=30)
        default_list.save(update_fields=("current_valid_from", "future_valid_from"))
        response = self.client.get(reverse("price_list_edit", args=(default_list.pk,)))
        self.assertContains(response, "Testata listino")
        grid_response = self.client.get(reverse("price_list_grid", args=(default_list.pk,)))
        self.assertContains(grid_response, "Prezzo passato")
        grid_save = self.client.post(
            reverse("price_list_grid", args=(default_list.pk,)),
            {
                f"current_{self.part.pk}": "50.00",
                f"future_{self.part.pk}": "55.00",
            },
        )
        self.assertEqual(grid_save.status_code, 302)
        item = PriceListItem.objects.get(price_list=default_list, part=self.part)
        self.assertEqual(item.unit_price, Decimal("50.00"))
        self.assertEqual(item.future_price, Decimal("55.00"))

    def test_customer_price_list_is_assigned_when_created_with_exceptions(self):
        self.client.force_login(self.reception_user)
        url = f'{reverse("price_list_create")}?customer={self.customer.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        save_response = self.client.post(
            url,
            {
                "code": self.customer.customer_code,
                "name": f"Listino {self.customer}",
                "customer": str(self.customer.pk),
                "current_valid_from": timezone.localdate().isoformat(),
                "is_active": "on",
            },
        )
        self.assertEqual(save_response.status_code, 302)
        price_list = PriceList.objects.get(
            workshop=self.workshop,
            code=self.customer.customer_code,
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.price_list_id, price_list.pk)

    def test_part_price_page_updates_default_and_regenerates_workshop(self):
        response = self.client.get(reverse("price_list_grid", args=(self.customer.price_list_id,)))
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.reception_user)
        workshop_list = PriceList.objects.get(workshop=self.workshop, is_workshop=True)
        default_list = PriceList.objects.get(workshop=self.workshop, is_default=True)
        for price_list, value in ((default_list, "100.00"), (workshop_list, "42.00")):
            save_response = self.client.post(
                reverse("price_list_grid", args=(price_list.pk,)),
                {f"current_{self.part.pk}": value},
            )
            self.assertEqual(save_response.status_code, 302)
        self.assertEqual(
            PriceListItem.objects.get(price_list=default_list, part=self.part).unit_price,
            Decimal("100.00"),
        )
        self.assertEqual(
            PriceListItem.objects.get(price_list=workshop_list, part=self.part).unit_price,
            Decimal("42.00"),
        )
        detail_response = self.client.get(reverse("part_detail", args=(self.part.pk,)))
        self.assertNotContains(detail_response, "Reference cost")
        self.assertNotContains(detail_response, "Manage prices")
        self.assertNotContains(detail_response, "Price lists and sales prices")

    def test_warehouse_hold_notifies_the_requesting_mechanic(self):
        item = PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.work_order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("1"),
            requested_by=self.mechanic,
            status="pending",
        )
        self.client.force_login(self.parts_user)

        self.client.post(reverse("parts_request_action", args=(item.pk, "hold")))

        item.refresh_from_db()
        self.assertEqual(item.status, "on_hold")
        self.assertTrue(
            Notification.objects.filter(
                user=self.mechanic,
                title="Part request on hold",
                work_order=self.work_order,
            ).exists()
        )

    def test_warehouse_reminder_cannot_be_resent_until_answered(self):
        item = PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.work_order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("1"),
            requested_by=self.mechanic,
            status="pending",
        )
        remind_url = reverse("parts_request_action", args=(item.pk, "remind"))

        self.client.post(remind_url)

        item.refresh_from_db()
        first_reminder_at = item.warehouse_reminder_sent_at
        self.assertIsNotNone(first_reminder_at)
        self.assertTrue(item.warehouse_reminder_pending)
        self.assertEqual(
            Notification.objects.filter(
                user=self.parts_user, title="Warehouse reminder", work_order=self.work_order
            ).count(),
            1,
        )

        self.client.post(remind_url)

        item.refresh_from_db()
        self.assertEqual(item.warehouse_reminder_sent_at, first_reminder_at)
        self.assertEqual(
            Notification.objects.filter(
                user=self.parts_user, title="Warehouse reminder", work_order=self.work_order
            ).count(),
            1,
        )

        self.client.force_login(self.parts_user)
        self.client.post(
            reverse("parts_request_action", args=(item.pk, "estimate")),
            {"eta_kind": "stock", "eta_value": "25"},
        )

        item.refresh_from_db()
        self.assertEqual(item.warehouse_eta_kind, "stock")
        self.assertEqual(item.warehouse_eta_value, 25)
        self.assertEqual(item.warehouse_eta_updated_by, self.parts_user)
        self.assertGreaterEqual(
            item.warehouse_reminder_answered_at, first_reminder_at
        )
        self.assertFalse(item.warehouse_reminder_pending)
        self.assertTrue(
            Notification.objects.filter(
                user=self.mechanic,
                title="Warehouse delivery estimate",
                body__contains="25 minutes",
                work_order=self.work_order,
            ).exists()
        )

        self.client.force_login(self.mechanic)
        self.client.post(remind_url)

        item.refresh_from_db()
        self.assertGreater(
            item.warehouse_reminder_sent_at, item.warehouse_reminder_answered_at
        )
        self.assertTrue(item.warehouse_reminder_pending)

    def test_supplier_estimate_is_displayed_in_days(self):
        item = PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.work_order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("1"),
            requested_by=self.mechanic,
            status="pending",
        )
        self.client.force_login(self.parts_user)

        self.client.post(
            reverse("parts_request_action", args=(item.pk, "estimate")),
            {"eta_kind": "supplier", "eta_value": "3"},
        )

        item.refresh_from_db()
        self.assertEqual(item.warehouse_eta_kind, "supplier")
        self.assertEqual(item.warehouse_eta_value, 3)
        self.assertTrue(
            Notification.objects.filter(
                user=self.mechanic,
                title="Warehouse delivery estimate",
                body__contains="3 days",
                work_order=self.work_order,
            ).exists()
        )

        self.client.force_login(self.mechanic)
        response = self.client.get(reverse("my_jobs"))

        self.assertContains(response, "Estimated delivery: 3 days")

    def test_mechanic_without_active_session_cannot_request_parts(self):
        self.participation.is_active = False
        self.participation.save(update_fields=("is_active",))

        response = self.client.post(
            reverse("job_parts_request", args=(self.job.pk,)),
            self._request_payload([{"part": str(self.part.pk), "quantity": "1"}]),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(PartsRequest.objects.exists())

    def test_job_actions_require_authentication(self):
        self.client.logout()

        response = self.client.post(reverse("job_action", args=(self.job.pk, "start")))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_technician_can_see_dashboard_link_and_personal_dashboard(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sidebar-dashboard"')
        self.assertContains(response, "My active sessions")
        self.assertContains(response, self.job.title)

    def test_mechanic_can_open_one_activity_for_an_order_without_activities(self):
        order = WorkOrder.objects.create(
            workshop=self.workshop,
            vehicle=self.camper,
            customer=self.customer,
            ro_number="RO-TEST-2",
        )

        response = self.client.post(
            reverse("mechanic_open_job", args=(order.pk,)),
            {"title": "Controllo freni", "description": "Verifica iniziale"},
        )

        activity = Job.objects.get(work_order=order)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(activity.job_number, 1)
        self.assertEqual(activity.title, "Controllo freni")
        self.assertRedirects(
            response,
            f'{reverse("work_order_detail", args=(order.pk,))}#job-{activity.pk}',
            fetch_redirect_response=False,
        )
        detail_response = self.client.get(reverse("work_order_detail", args=(order.pk,)))
        self.assertContains(detail_response, f"{order.ro_number}-01")

    def test_mechanic_cannot_open_another_activity_for_an_order_with_one(self):
        response = self.client.post(
            reverse("mechanic_open_job", args=(self.work_order.pk,)),
            {"title": "Attività duplicata"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Job.objects.filter(work_order=self.work_order).count(), 1)

    def test_mechanic_cannot_advance_order_with_open_activity(self):
        response = self.client.post(
            reverse("order_status", args=(self.work_order.pk,)),
            {"status": "ready_inspection"},
        )

        self.assertEqual(response.status_code, 302)
        self.work_order.refresh_from_db()
        self.assertEqual(self.work_order.status, "open")

    def test_opening_work_order_marks_warehouse_notes_read(self):
        another_mechanic = get_user_model().objects.create_user(
            "another-mechanic",
            "another-mechanic@example.test",
            "password",
            profile="mechanic",
        )
        Membership.objects.create(user=another_mechanic, workshop=self.workshop)
        note = WarehouseNote.objects.create(
            workshop=self.workshop,
            work_order=self.work_order,
            part=self.part,
            author=self.parts_user,
            text="Ricambio non disponibile.",
        )
        read_receipt = WarehouseNoteRead.objects.create(
            note=note,
            recipient=self.mechanic,
        )
        unread_receipt = WarehouseNoteRead.objects.create(
            note=note,
            recipient=another_mechanic,
        )

        response = self.client.get(reverse("work_order_detail", args=(self.work_order.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ricambio non disponibile.")
        read_receipt.refresh_from_db()
        unread_receipt.refresh_from_db()
        self.assertIsNotNone(read_receipt.read_at)
        self.assertIsNone(unread_receipt.read_at)

    def test_orders_menu_lists_work_orders_before_quotes(self):
        office_user = get_user_model().objects.create_user(
            "orders-office", "orders-office@example.test", "password", profile="admin"
        )
        Membership.objects.create(
            user=office_user, workshop=self.workshop
        )
        self.client.force_login(office_user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workshop jobs")
        content = response.content.decode()
        orders_group = content.index('<summary class="sidebar-label">Orders</summary>')
        work_orders_link = content.index(f'href="{reverse("orders")}"', orders_group)
        quotes_link = content.index(f'href="{reverse("quotes")}"', orders_group)
        self.assertLess(work_orders_link, quotes_link)

    def test_my_jobs_displays_inline_request_formset(self):
        response = self.client.get(reverse("my_jobs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="" selected disabled></option>')
        self.assertContains(response, "Active")
        self.assertContains(response, "Finish session and record parts used")
        self.assertContains(response, reverse("job_parts_request", args=(self.job.pk,)))
        self.assertContains(response, "parts-%s-TOTAL_FORMS" % self.job.pk)
        self.assertContains(response, "data-confirm=")
        self.assertContains(response, "data-part-search")
        self.assertContains(response, 'data-search="filter-1 oil filter"')
        self.assertContains(response, 'data-unit="pz"')
        self.assertContains(response, "data-part-unit-output")
        self.assertNotContains(response, "Other part")

    def test_paused_session_shows_reason_and_resume_action(self):
        reason = PauseReason.objects.create(code="waiting", label="Waiting for approval")
        self.participation.paused_at = timezone.now()
        self.participation.save(update_fields=("paused_at",))
        TimeEvent.objects.create(
            workshop=self.workshop,
            job=self.job,
            mechanic=self.mechanic,
            event_type="pause",
            pause_reason=reason,
            event_at=self.participation.paused_at,
        )

        response = self.client.get(reverse("my_jobs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paused")
        self.assertContains(response, "Waiting for approval")
        self.assertContains(response, "Resume timer")

    def test_recent_closed_session_is_visible(self):
        self.participation.is_active = False
        self.participation.finished_at = timezone.now()
        self.participation.save(update_fields=("is_active", "finished_at"))

        response = self.client.get(reverse("my_jobs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent sessions")
        self.assertContains(response, "Session closed")
        self.assertContains(response, self.job.title)

    def test_pause_requires_an_explicit_reason(self):
        response = self.client.post(
            reverse("job_action", args=(self.job.pk, "pause")),
            {"pause_reason": ""},
        )

        self.assertEqual(response.status_code, 302)
        self.participation.refresh_from_db()
        self.assertTrue(self.participation.is_active)
        self.assertIsNone(self.participation.paused_at)
        self.assertFalse(TimeEvent.objects.filter(job=self.job, event_type="pause").exists())

    def test_finish_session_reserves_stock_without_deducting_until_order_closure(self):
        response = self.client.post(
            reverse("job_complete", args=(self.job.pk,)),
            self._completion_payload([{"part": str(self.part.pk), "quantity": "3"}]),
        )

        self.assertEqual(response.status_code, 302)
        self.part.refresh_from_db()
        self.participation.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(self.part.quantity, Decimal("10"))
        self.assertFalse(self.participation.is_active)
        self.assertEqual(self.job.status, "completed")
        transfer_line = TransferSlipLine.objects.get(part=self.part, job=self.job)
        self.assertEqual(transfer_line.quantity_reserved, Decimal("3"))
        self.assertFalse(JobPartUsage.objects.exists())
        self.assertFalse(PartMovement.objects.exists())
        self.assertTrue(TimeEvent.objects.filter(job=self.job, event_type="finish").exists())

    def test_finish_session_requires_confirmation_even_when_no_parts_were_used(self):
        response = self.client.post(
            reverse("job_complete", args=(self.job.pk,)),
            self._completion_payload(confirmed=False),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["confirmation_error"])
        self.participation.refresh_from_db()
        self.assertTrue(self.participation.is_active)
        self.assertFalse(JobPartUsage.objects.exists())

    def test_insufficient_stock_keeps_session_active_and_records_nothing(self):
        self.part.quantity = Decimal("2")
        self.part.save(update_fields=("quantity",))
        response = self.client.post(
            reverse("job_complete", args=(self.job.pk,)),
            self._completion_payload([{"part": str(self.part.pk), "quantity": "3"}]),
        )

        self.assertEqual(response.status_code, 200)
        self.part.refresh_from_db()
        self.participation.refresh_from_db()
        self.assertEqual(self.part.quantity, Decimal("2"))
        self.assertTrue(self.participation.is_active)
        self.assertFalse(JobPartUsage.objects.exists())
        self.assertFalse(PartMovement.objects.exists())

    def test_delivered_request_is_not_decremented_again_at_session_finish(self):
        self.part.quantity = Decimal("8")
        self.part.save(update_fields=("quantity",))
        PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.work_order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("2"),
            quantity_delivered=Decimal("2"),
            status="delivered",
            inventory_applied=True,
        )

        self.client.post(
            reverse("job_complete", args=(self.job.pk,)),
            self._completion_payload(),
        )

        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, Decimal("8"))
        self.assertFalse(JobPartUsage.objects.exists())

    def test_work_order_pdf_renders_stock_usage(self):
        user_model = get_user_model()
        office_user = user_model.objects.create_user(
            "office", "office@example.test", "password", profile="admin"
        )
        Membership.objects.create(
            user=office_user, workshop=self.workshop
        )
        self.work_order.status = "completed"
        self.work_order.completed_at = timezone.now()
        self.work_order.save(update_fields=("status", "completed_at"))
        JobPartUsage.objects.create(
            workshop=self.workshop, job=self.job, part=self.part,
            quantity_used=Decimal("1"), used_by=self.mechanic,
        )
        self.client.force_login(office_user)

        response = self.client.post(
            reverse("work_order_report", args=(self.work_order.pk,)), {"mark_invoiced": "0"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))


class WorkflowModelOwnershipMigrationTests(TransactionTestCase):
    migrate_from = [
        ("clientandsuppliers", "0005_camperowner_price_list"),
        ("fleet", "0009_warehousenote_warehousenoteread_and_more"),
        ("orders", "0016_alter_job_status_alter_workorder_status"),
        ("parts", "0008_alter_purchaseorder_options"),
    ]
    migrate_to = [
        ("clientandsuppliers", "0006_alter_contactdocument_category"),
        ("fleet", "0010_move_workflow_models"),
        ("orders", "0018_warrantyreturn_parts_request_and_more"),
        ("parts", "0009_alter_partdocument_category_partsrequest_and_more"),
    ]

    def _migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def setUp(self):
        super().setUp()
        old_apps = self._migrate(self.migrate_from)
        old_category_model = old_apps.get_model("fleet", "DocumentCategory")
        self.category = old_category_model.objects.create(
            code="migration-check",
            name="Migration check",
        )
        content_type_model = old_apps.get_model("contenttypes", "ContentType")
        permission_model = old_apps.get_model("auth", "Permission")
        content_type = content_type_model.objects.get(
            app_label="fleet",
            model="documentcategory",
        )
        self.permission = permission_model.objects.create(
            name="Can verify migrated category",
            codename="verify_migrated_category",
            content_type=content_type,
        )
        self.category_id = self.category.pk
        self.content_type_id = content_type.pk
        self.permission_id = self.permission.pk
        self._migrate(self.migrate_to)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_table_data_and_permission_content_type_survive_forward_and_reverse(self):
        apps = self._migrate(self.migrate_to)
        category_model = apps.get_model("orders", "DocumentCategory")
        content_type_model = apps.get_model("contenttypes", "ContentType")
        permission_model = apps.get_model("auth", "Permission")

        self.assertEqual(category_model._meta.db_table, "orders_documentcategory")
        self.assertTrue(category_model.objects.filter(pk=self.category_id).exists())
        moved_type = content_type_model.objects.get(pk=self.content_type_id)
        self.assertEqual((moved_type.app_label, moved_type.model), ("orders", "documentcategory"))
        self.assertTrue(
            permission_model.objects.filter(
                pk=self.permission_id,
                content_type_id=self.content_type_id,
            ).exists()
        )

        old_apps = self._migrate(self.migrate_from)
        old_category_model = old_apps.get_model("fleet", "DocumentCategory")
        self.assertEqual(old_category_model._meta.db_table, "fleet_documentcategory")
        self.assertTrue(old_category_model.objects.filter(pk=self.category_id).exists())
        restored_type = old_apps.get_model("contenttypes", "ContentType").objects.get(
            pk=self.content_type_id
        )
        self.assertEqual((restored_type.app_label, restored_type.model), ("fleet", "documentcategory"))

        apps = self._migrate(self.migrate_to)
        self.assertTrue(
            apps.get_model("orders", "DocumentCategory").objects.filter(pk=self.category_id).exists()
        )
