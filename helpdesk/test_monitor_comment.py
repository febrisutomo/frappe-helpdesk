import frappe
from frappe.tests import IntegrationTestCase

from helpdesk.helpdesk.doctype.hd_ticket.hd_ticket import comment_has_permission

MONITOR = "monitor-comment-test@example.com"


class TestMonitorComment(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("Role", "Ticket Monitor"):  # created by the Dimensy setup scripts, not by the app
			frappe.get_doc({"doctype": "Role", "role_name": "Ticket Monitor", "desk_access": 1}).insert(ignore_permissions=True)
		if not frappe.db.exists("User", MONITOR):
			frappe.get_doc({"doctype": "User", "email": MONITOR, "first_name": "Monitor", "send_welcome_email": 0,
				"roles": [{"role": "Agent Manager"}, {"role": "Ticket Monitor"}]}).insert(ignore_permissions=True)
		self.ticket = frappe.get_doc({"doctype": "HD Ticket", "subject": "monitor comment test", "raised_by": "someone@example.com"}).insert(ignore_permissions=True)
		self.comment = frappe._dict(reference_ticket=self.ticket.name)

	def test_monitor_may_create_a_comment_only(self):
		self.assertTrue(comment_has_permission(self.comment, "create", MONITOR))
		self.assertTrue(comment_has_permission(self.comment, "read", MONITOR))
		for ptype in ("write", "delete"):
			self.assertFalse(comment_has_permission(self.comment, ptype, MONITOR), ptype)

	def test_monitor_still_cannot_change_the_ticket(self):
		self.assertFalse(frappe.has_permission("HD Ticket", "write", doc=self.ticket.name, user=MONITOR))
		self.assertFalse(frappe.has_permission(doc=frappe.new_doc("HD Ticket"), ptype="create", user=MONITOR))

	def test_a_comment_is_always_written_by_its_sender(self):
		frappe.set_user(MONITOR)
		try:
			c = frappe.get_doc({"doctype": "HD Ticket Comment", "reference_ticket": self.ticket.name, "content": "<p>x</p>",
				"commented_by": "Administrator", "is_pinned": 1}).insert(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(c.commented_by, MONITOR)
		self.assertFalse(c.is_pinned)

	def test_monitor_cannot_attach_files_to_a_comment(self):
		frappe.set_user(MONITOR)
		try:
			self.assertRaises(frappe.PermissionError, self.ticket.new_comment, "<p>x</p>", [{"file_url": "/private/files/other.pdf"}])
		finally:
			frappe.set_user("Administrator")

	def test_the_author_of_a_saved_comment_cannot_be_changed(self):
		c = frappe.get_doc({"doctype": "HD Ticket Comment", "reference_ticket": self.ticket.name, "content": "<p>x</p>"}).insert(ignore_permissions=True)
		author = c.commented_by
		frappe.set_user(MONITOR)
		try:
			c.reload()
			c.commented_by = MONITOR
			c.save(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("HD Ticket Comment", c.name, "commented_by"), author)
