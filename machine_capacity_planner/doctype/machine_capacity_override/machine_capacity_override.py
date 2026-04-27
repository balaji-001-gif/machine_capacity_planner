"""Machine Capacity Override — applies manual override to Job Card on insert."""
import frappe
from frappe.model.document import Document
from machine_capacity_planner.utils.logger import mcp_logger


class MachineCapacityOverride(Document):
    def after_insert(self):
        """Apply the override to the linked Job Card immediately after saving."""
        jc = frappe.get_doc("Job Card", self.job_card)

        # Record auto-assigned machine for audit trail
        self.db_set("auto_machine", jc.workstation)

        # Apply override
        frappe.db.set_value("Job Card", self.job_card, {
            "workstation":         self.override_machine,
            "custom_allocated_by": f"MANUAL:{frappe.session.user}",
        })

        mcp_logger.info(
            f"[MCP Override] JC {self.job_card}: "
            f"{jc.workstation} → {self.override_machine} "
            f"by {frappe.session.user} | Reason: {self.reason}"
        )

        frappe.msgprint(
            f"Override applied: {self.job_card} reassigned to {self.override_machine}.",
            alert=True,
            indicator="blue",
        )
