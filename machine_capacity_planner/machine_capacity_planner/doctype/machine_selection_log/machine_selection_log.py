"""Machine Selection Log — controller."""
import frappe
from frappe.model.document import Document


class MachineSelectionLog(Document):
    def before_insert(self):
        if not self.get("creation"):
            self.creation = frappe.utils.now_datetime()
