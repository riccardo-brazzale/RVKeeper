import json
import logging
from datetime import datetime, timezone


class StructuredContextFormatter(logging.Formatter):
    CONTEXT_FIELDS = (
        "work_order_id",
        "activity_id",
        "part_id",
        "parts_request_id",
        "transfer_slip_id",
        "purchase_order_id",
        "purchase_order_line_id",
        "supplier_id",
        "note_id",
        "user_id",
        "transition",
        "quantity_requested",
        "quantity_reserved",
        "quantity_received",
        "new_status",
    )

    def format(self, record):
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self.CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)
