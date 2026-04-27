"""Material Readiness Override — stamps override_date on insert."""
import frappe
from frappe.model.document import Document


class MaterialReadinessOverride(Document):
    def before_insert(self):
        self.override_date = frappe.utils.now_datetime()
        self.confirmed_by  = frappe.session.user
