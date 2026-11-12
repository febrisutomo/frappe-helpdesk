import frappe
from frappe.desk.form.assign_to import add as assign
from frappe.tests import IntegrationTestCase

ASSIGNER = "escalation-assign-test@example.com"  # the CTO: monitor + SLA Escalation
MONITOR = "escalation-monitor-test@example.com"  # the Manajer PSrE: monitor only
AGENT = "escalation-agent-test@example.com"


def _user(email, roles):
	for role in roles:
		if not frappe.db.exists("Role", role):  # created by the Dimensy setup scripts, not by the app
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
	if not frappe.db.exists("User", email):
		frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0,
			"roles": [{"role": r} for r in roles]}).insert(ignore_permissions=True)


class TestEscalationAssign(IntegrationTestCase):
	def setUp(self):
		_user(ASSIGNER, ["Agent Manager", "Ticket Monitor", "SLA Escalation"])
		_user(MONITOR, ["Agent Manager", "Ticket Monitor"])
		_user(AGENT, ["Agent"])
		if not frappe.db.exists("HD Agent", AGENT):
			frappe.get_doc({"doctype": "HD Agent", "user": AGENT, "agent_name": "agent"}).insert(ignore_permissions=True)
		self.ticket = frappe.get_doc({"doctype": "HD Ticket", "subject": "escalation assign test", "raised_by": "someone@example.com"}).insert(ignore_permissions=True)

	def _assign_as(self, user, assignee):
		frappe.set_user(user)
		try:
			assign({"doctype": "HD Ticket", "name": self.ticket.name, "assign_to": [assignee]})
		finally:
			frappe.set_user("Administrator")

	def test_escalation_monitor_may_assign_an_agent(self):
		self._assign_as(ASSIGNER, AGENT)
		self.assertTrue(frappe.db.exists("ToDo", {"reference_name": self.ticket.name, "allocated_to": AGENT, "status": "Open"}))

	def test_plain_monitor_still_cannot_assign(self):
		self.assertRaises(frappe.PermissionError, self._assign_as, MONITOR, AGENT)

	def test_no_monitor_is_ever_assigned(self):
		self.assertRaises(frappe.PermissionError, self._assign_as, ASSIGNER, MONITOR)
		self.assertRaises(frappe.PermissionError, self._assign_as, ASSIGNER, ASSIGNER)

	def test_escalation_monitor_still_cannot_change_the_ticket(self):
		self.assertFalse(frappe.has_permission("HD Ticket", "write", doc=self.ticket.name, user=ASSIGNER))
