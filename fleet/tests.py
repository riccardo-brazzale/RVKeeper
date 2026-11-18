from decimal import Decimal
from datetime import datetime
from io import BytesIO, StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from clientandsuppliers.models import CamperOwner
from orders.models import Job, PauseReason, WorkOrder
from parts.models import Part, PartMovement
from workshops.models import Membership, Workshop

from .forms import CamperForm, WorkOrderForm
from .models import Camper, JobPartUsage, JobParticipation, Notification, PartsRequest, TimeEvent


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
        demo_customer = CamperOwner.objects.get(
            workshop=self.workshop,
            email="emily.carter@contacts.example",
        )
        self.assertIn("Profilo demo fittizio", demo_customer.notes)
        demo_part = Part.objects.get(workshop=self.workshop, part_number="DEMO-PART-001")
        self.assertEqual(demo_part.sale_price, Decimal("14.16"))
        self.assertIn("amsoil.com", demo_part.description)
        stock_before_rerun = dict(
            Part.objects.filter(workshop=self.workshop).values_list("pk", "quantity")
        )

        demo_customer.notes = "Old demo note"
        demo_customer.save(update_fields=("notes",))
        demo_part.name = "Old demo name"
        demo_part.sale_price = Decimal("999.99")
        demo_part.save(update_fields=("name", "sale_price"))
        self._run_command()

        demo_customer.refresh_from_db()
        demo_part.refresh_from_db()
        self.assertIn("Profilo demo fittizio", demo_customer.notes)
        self.assertEqual(demo_part.name, "Engine oil filter")
        self.assertEqual(demo_part.sale_price, Decimal("14.16"))
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
        self.part.sale_price = Decimal("150.00")
        self.part.save(update_fields=("sale_price",))

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

    def test_mechanic_without_active_session_cannot_request_parts(self):
        self.participation.is_active = False
        self.participation.save(update_fields=("is_active",))

        response = self.client.post(
            reverse("job_parts_request", args=(self.job.pk,)),
            self._request_payload([{"part": str(self.part.pk), "quantity": "1"}]),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(PartsRequest.objects.exists())

    def test_technician_can_see_dashboard_link_and_personal_dashboard(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sidebar-dashboard"')
        self.assertContains(response, "My active sessions")
        self.assertContains(response, self.job.title)

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

    def test_finish_session_records_additional_stock_usage_atomically(self):
        response = self.client.post(
            reverse("job_complete", args=(self.job.pk,)),
            self._completion_payload([{"part": str(self.part.pk), "quantity": "3"}]),
        )

        self.assertEqual(response.status_code, 302)
        self.part.refresh_from_db()
        self.participation.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(self.part.quantity, Decimal("7"))
        self.assertFalse(self.participation.is_active)
        self.assertEqual(self.job.status, "completed")
        self.assertEqual(JobPartUsage.objects.get().quantity_used, Decimal("3"))
        movement = PartMovement.objects.get()
        self.assertEqual(movement.movement_type, "out")
        self.assertEqual(movement.quantity, Decimal("3"))
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
