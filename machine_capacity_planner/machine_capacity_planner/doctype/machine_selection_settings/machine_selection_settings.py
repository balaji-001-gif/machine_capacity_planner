"""Machine Selection Settings — validates weights sum to 100."""
import frappe
from frappe.model.document import Document


class MachineSelectionSettings(Document):
    def validate(self):
        total = (
            (self.weight_load or 0)
            + (self.weight_free_slot or 0)
            + (self.weight_delivery_slack or 0)
            + (self.weight_maintenance_risk or 0)
            + (self.weight_material_readiness or 0)
        )
        if total != 100:
            frappe.throw(
                f"Scoring weights must sum to 100 (includes Material Readiness). "
                f"Current total: {total}. Recommended: 25+25+20+10+20 = 100.",
                title="Invalid Weight Configuration",
            )
