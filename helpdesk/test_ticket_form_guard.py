import frappe
from frappe.tests import UnitTestCase

from helpdesk.utils import _called_method, _method_target


class TestTicketFormGuard(UnitTestCase):
    def test_called_method_reads_the_dotted_name_from_every_route(self):
        name = "frappe.desk.form.load.getdoc"
        self.assertEqual(_called_method(f"/api/method/{name}", {}), name)
        self.assertEqual(_called_method(f"/api/method/{name}/", {}), name)
        self.assertEqual(_called_method(f"/api/v2/method/{name}", {}), name)
        self.assertEqual(_called_method("/api/method/frappe%2Edesk%2Eform%2Eload%2Egetdoc", {}), name)
        self.assertEqual(_called_method("/", {"cmd": name}), name)
        self.assertEqual(_called_method("/api/resource/HD Ticket", {}), "")

    def test_method_target_reads_the_document_from_args_or_doc(self):
        self.assertEqual(_method_target({"doctype": "HD Ticket", "name": "1"}), ("HD Ticket", "1"))
        self.assertEqual(
            _method_target({"args": '{"doctype": "HD Ticket", "name": "2"}'}), ("HD Ticket", "2")
        )
        self.assertEqual(_method_target({"doc": {"doctype": "HD Ticket", "name": "3"}}), ("HD Ticket", "3"))
        self.assertEqual(_method_target({}), ("", ""))
