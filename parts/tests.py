from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from clientandsuppliers.models import CamperOwner
from orders.models import Job, WorkOrder
from workshops.models import Membership, Workshop

from .models import (
    GoodsReceiptLine,
    GoodsReceipt,
    JobPartUsage,
    Part,
    PartMovement,
    PartSupplierOffer,
    PartsRequest,
    PurchaseOrder,
    PurchaseOrderLine,
    SupplierPriceList,
    SupplierPriceListItem,
    TransferSlip,
    TransferSlipLine,
)
from .services import (
    add_request_to_purchase_order,
    cancel_transfer_slip,
    close_transfer_slip,
    receive_purchase_order_line,
    round_order_quantity,
    reserve_job_usage,
    reserve_parts_request,
    supplier_price_for_date,
)


class InventoryServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="magazziniere",
            email="magazziniere@example.test",
            password="password",
            profile="warehouse",
        )
        self.workshop = Workshop.objects.create(name="Officina test", slug="officina-test")
        Membership.objects.create(user=self.user, workshop=self.workshop)
        self.mechanic = get_user_model().objects.create_user(
            username="meccanico",
            email="meccanico@example.test",
            password="password",
            profile="mechanic",
        )
        Membership.objects.create(user=self.mechanic, workshop=self.workshop)
        self.supplier = CamperOwner.objects.create(
            workshop=self.workshop,
            kind="supplier",
            is_company=True,
            company_name="Fornitore test",
        )
        self.part = Part.objects.create(
            workshop=self.workshop,
            part_number="FILTRO-1",
            name="Filtro olio",
            quantity=Decimal("10"),
        )
        self.order = WorkOrder.objects.create(
            workshop=self.workshop,
            ro_number="RO-2026-0001",
        )
        self.job = Job.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            job_number=1,
            title="Sostituzione filtro",
        )

    def test_rounding_respects_minimum_then_rounds_up_to_package_multiple(self):
        self.assertEqual(
            round_order_quantity(Decimal("5"), Decimal("6"), Decimal("4")),
            Decimal("8"),
        )
        self.assertEqual(
            round_order_quantity(Decimal("9"), Decimal("6"), Decimal("4")),
            Decimal("12"),
        )

    def test_supplier_price_list_is_selected_by_effective_date(self):
        earlier = SupplierPriceList.objects.create(
            workshop=self.workshop,
            supplier=self.supplier,
            code="2026-01",
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 5, 31),
        )
        current = SupplierPriceList.objects.create(
            workshop=self.workshop,
            supplier=self.supplier,
            code="2026-06",
            valid_from=date(2026, 6, 1),
        )
        SupplierPriceListItem.objects.create(
            price_list=earlier,
            supplier_article_code="EXT-1",
            part=self.part,
            unit_price=Decimal("8.50"),
        )
        current_item = SupplierPriceListItem.objects.create(
            price_list=current,
            supplier_article_code="EXT-1",
            part=self.part,
            unit_price=Decimal("9.25"),
        )

        self.assertEqual(
            supplier_price_for_date(self.part, self.supplier, date(2026, 7, 1)),
            current_item,
        )

    def test_order_request_uses_valid_list_price_and_rounds_quantity(self):
        self.part.quantity = Decimal("0")
        self.part.save(update_fields=("quantity",))
        offer = PartSupplierOffer.objects.create(
            part=self.part,
            supplier=self.supplier,
            supplier_code="EXT-1",
            purchase_price=Decimal("10.00"),
            minimum_order_quantity=Decimal("6"),
            package_multiple=Decimal("4"),
            is_preferred=True,
        )
        price_list = SupplierPriceList.objects.create(
            workshop=self.workshop,
            supplier=self.supplier,
            code="LISTINO",
            valid_from=date(2026, 1, 1),
        )
        SupplierPriceListItem.objects.create(
            price_list=price_list,
            supplier_article_code="EXT-1",
            part=self.part,
            unit_price=Decimal("8.00"),
            discount_percent=Decimal("5.00"),
        )
        request = PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("5"),
        )

        purchase_order = add_request_to_purchase_order(
            request,
            user=self.user,
            effective_date=date(2026, 7, 1),
        )

        line = PurchaseOrderLine.objects.get(purchase_order=purchase_order, part=self.part)
        self.assertEqual(purchase_order.supplier, self.supplier)
        self.assertEqual(line.supplier_offer, offer)
        self.assertEqual(line.quantity_ordered, Decimal("8"))
        self.assertEqual(line.unit_price, Decimal("8.00"))
        self.assertEqual(line.discount_percent, Decimal("5.00"))

    def test_preferred_supplier_is_used_when_multiple_offers_exist(self):
        self.part.quantity = Decimal("0")
        self.part.save(update_fields=("quantity",))
        preferred_supplier = CamperOwner.objects.create(
            workshop=self.workshop,
            kind="supplier",
            is_company=True,
            company_name="Fornitore preferito",
        )
        preferred_offer = PartSupplierOffer.objects.create(
            part=self.part,
            supplier=preferred_supplier,
            purchase_price=Decimal("20.00"),
            is_preferred=True,
        )
        PartSupplierOffer.objects.create(
            part=self.part,
            supplier=self.supplier,
            purchase_price=Decimal("1.00"),
        )
        request = PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("1"),
        )

        purchase_order = add_request_to_purchase_order(request, user=self.user)

        self.assertEqual(purchase_order.supplier, preferred_supplier)
        self.assertEqual(
            purchase_order.lines.get(part=self.part).supplier_offer,
            preferred_offer,
        )

    def test_purchase_order_only_contains_the_unreserved_quantity(self):
        self.part.quantity = Decimal("2")
        self.part.save(update_fields=("quantity",))
        PartSupplierOffer.objects.create(
            part=self.part,
            supplier=self.supplier,
            purchase_price=Decimal("10.00"),
            minimum_order_quantity=Decimal("1"),
            package_multiple=Decimal("1"),
            is_preferred=True,
        )
        request = PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("5"),
        )
        reserve_parts_request(request, user=self.user)

        purchase_order = add_request_to_purchase_order(request, user=self.user)

        line = purchase_order.lines.get(part=self.part)
        demand = line.demands.get(parts_request=request)
        self.assertEqual(line.quantity_required, Decimal("3"))
        self.assertEqual(line.quantity_ordered, Decimal("3"))
        self.assertEqual(demand.quantity_requested, Decimal("3"))

    def test_transfer_slip_consumes_reserved_stock_only_when_order_closes(self):
        slip = TransferSlip.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            created_by=self.user,
        )
        TransferSlipLine.objects.create(
            transfer_slip=slip,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("3"),
            quantity_reserved=Decimal("3"),
            status="reserved",
        )

        close_transfer_slip(self.order, user=self.user)

        self.part.refresh_from_db()
        slip.refresh_from_db()
        self.assertEqual(self.part.quantity, Decimal("7"))
        self.assertEqual(slip.status, "closed")
        self.assertEqual(PartMovement.objects.get().movement_type, "out")
        self.assertEqual(JobPartUsage.objects.get().quantity_used, Decimal("3"))

    def test_cancelling_order_releases_reservations_without_stock_movement(self):
        slip = TransferSlip.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            created_by=self.user,
        )
        line = TransferSlipLine.objects.create(
            transfer_slip=slip,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("3"),
            quantity_reserved=Decimal("3"),
            status="reserved",
        )

        cancel_transfer_slip(self.order, user=self.user)

        self.part.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(self.part.quantity, Decimal("10"))
        self.assertEqual(line.status, "released")
        self.assertEqual(line.quantity_reserved, Decimal("0"))
        self.assertFalse(PartMovement.objects.exists())

    def test_additional_usage_does_not_replace_a_parts_request_reservation(self):
        slip = TransferSlip.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            created_by=self.user,
        )
        request = PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("2"),
        )
        requested_line = TransferSlipLine.objects.create(
            transfer_slip=slip,
            job=self.job,
            parts_request=request,
            part=self.part,
            quantity_requested=Decimal("2"),
            quantity_reserved=Decimal("2"),
            status="reserved",
        )

        reserve_job_usage(self.job, {self.part.pk: Decimal("3")}, user=self.user)

        requested_line.refresh_from_db()
        additional_line = TransferSlipLine.objects.get(
            transfer_slip=slip,
            job=self.job,
            parts_request__isnull=True,
        )
        self.assertEqual(requested_line.quantity_reserved, Decimal("2"))
        self.assertEqual(additional_line.quantity_reserved, Decimal("3"))
        self.assertEqual(additional_line.quantity_requested, Decimal("3"))

    def test_receiving_order_partially_updates_stock_and_fulfills_waiting_request(self):
        self.part.quantity = Decimal("1")
        self.part.save(update_fields=("quantity",))
        PartSupplierOffer.objects.create(
            part=self.part,
            supplier=self.supplier,
            supplier_code="EXT-1",
            purchase_price=Decimal("10.00"),
            minimum_order_quantity=Decimal("1"),
            package_multiple=Decimal("2"),
            is_preferred=True,
        )
        request = PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("3"),
        )
        reserve_parts_request(request, user=self.user)
        purchase_order = add_request_to_purchase_order(request, user=self.user)
        line = PurchaseOrderLine.objects.get(purchase_order=purchase_order, part=self.part)
        self.assertEqual(line.quantity_required, Decimal("2"))
        self.assertEqual(line.quantity_ordered, Decimal("2"))

        receipt = receive_purchase_order_line(
            line,
            Decimal("1"),
            user=self.user,
            receipt_number="ENT-001",
        )

        self.part.refresh_from_db()
        line.refresh_from_db()
        purchase_order.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(self.part.quantity, Decimal("2"))
        self.assertEqual(line.quantity_received, Decimal("1"))
        self.assertEqual(purchase_order.status, "partially_received")
        self.assertNotEqual(request.status, "ready_for_pickup")

        receive_purchase_order_line(
            line,
            Decimal("1"),
            user=self.user,
            receipt_number="ENT-001",
        )

        self.part.refresh_from_db()
        line.refresh_from_db()
        request.refresh_from_db()
        purchase_order.refresh_from_db()
        receipt.refresh_from_db()
        self.assertEqual(self.part.quantity, Decimal("3"))
        self.assertEqual(line.quantity_received, Decimal("2"))
        self.assertEqual(purchase_order.status, "closed")
        self.assertEqual(request.status, "ready_for_pickup")
        self.assertEqual(receipt.lines.get(purchase_order_line=line).quantity_received, Decimal("2"))
        self.assertEqual(GoodsReceiptLine.objects.count(), 1)

    def test_supplier_article_code_is_searchable_and_purchase_access_is_role_checked(self):
        PartSupplierOffer.objects.create(
            part=self.part,
            supplier=self.supplier,
            supplier_code="EXT-FILTER-99",
            purchase_price=Decimal("10.00"),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("inventory"), {"q": "EXT-FILTER-99"})
        self.assertContains(response, self.part.part_number)

        self.client.force_login(self.mechanic)
        response = self.client.get(reverse("purchase_order_list"))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse("part_movement", args=(self.part.pk,)),
            {"quantity": "1", "movement_type": "in"},
        )
        self.assertEqual(response.status_code, 403)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, Decimal("10"))
        permission = Permission.objects.get(
            codename="manage_supplier_purchasing",
            content_type__app_label="parts",
            content_type__model="purchaseorder",
        )
        purchasing_group = Group.objects.create(name="Acquisti")
        purchasing_group.permissions.add(permission)
        self.mechanic.groups.add(purchasing_group)
        self.mechanic.refresh_from_db()
        self.client.force_login(self.mechanic)
        response = self.client.get(reverse("purchase_order_list"))
        self.assertEqual(response.status_code, 200)
        self.part.quantity = Decimal("0")
        self.part.save(update_fields=("quantity",))
        offer = PartSupplierOffer.objects.get(part=self.part, supplier=self.supplier)
        offer.supplier_code = "EXT-1"
        offer.save(update_fields=("supplier_code",))
        request = PartsRequest.objects.create(
            workshop=self.workshop,
            work_order=self.order,
            job=self.job,
            part=self.part,
            quantity_requested=Decimal("1"),
            status="on_hold",
        )
        response = self.client.post(
            reverse("parts_request_action", args=(request.pk, "order")),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PurchaseOrder.objects.exists())

    def test_purchase_order_and_receipt_documents_are_pdf(self):
        purchase_order = PurchaseOrder.objects.create(
            workshop=self.workshop,
            supplier=self.supplier,
            order_number="OF-2026-0001",
            order_date=date(2026, 7, 1),
            created_by=self.user,
        )
        line = PurchaseOrderLine.objects.create(
            purchase_order=purchase_order,
            part=self.part,
            quantity_required=Decimal("1"),
            quantity_ordered=Decimal("1"),
            unit_price=Decimal("10.00"),
        )
        receipt = GoodsReceipt.objects.create(
            workshop=self.workshop,
            purchase_order=purchase_order,
            receipt_number="ENT-002",
            received_by=self.user,
        )
        GoodsReceiptLine.objects.create(
            goods_receipt=receipt,
            purchase_order_line=line,
            quantity_received=Decimal("1"),
        )
        self.client.force_login(self.user)

        purchase_pdf = self.client.get(reverse("purchase_order_pdf", args=(purchase_order.pk,)))
        receipt_pdf = self.client.get(reverse("goods_receipt_pdf", args=(receipt.pk,)))

        self.assertEqual(purchase_pdf["Content-Type"], "application/pdf")
        self.assertTrue(purchase_pdf.content.startswith(b"%PDF"))
        self.assertEqual(receipt_pdf["Content-Type"], "application/pdf")
        self.assertTrue(receipt_pdf.content.startswith(b"%PDF"))

    def test_supplier_price_list_csv_import_reports_invalid_rows(self):
        upload = SimpleUploadedFile(
            "listino.csv",
            (
                "supplier_article_code,internal_article_code,unit_price,discount_percent\n"
                "EXT-FILTER-1,FILTRO-1,8.50,5\n"
                "EXT-BAD,MISSING,not-a-price,0\n"
            ).encode(),
            content_type="text/csv",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("supplier_price_list_import"),
            {
                "supplier": self.supplier.pk,
                "code": "CSV-2026",
                "name": "Listino CSV",
                "valid_from": "2026-07-01",
                "file": upload,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Riga 3")
        price_list = SupplierPriceList.objects.get(code="CSV-2026")
        self.assertEqual(price_list.items.count(), 1)
        self.assertEqual(price_list.items.get().supplier_article_code, "EXT-FILTER-1")
