import frappe
from frappe.tests import UnitTestCase

from helpdesk.utils import _called_method, _method_targets


class TestTicketFormGuard(UnitTestCase):
    def test_called_method_reads_the_dotted_name_from_every_route(self):
        name = "frappe.desk.form.load.getdoc"
        self.assertEqual(_called_method(f"/api/method/{name}", {}), name)
        self.assertEqual(_called_method(f"/api/method/{name}/", {}), name)
        self.assertEqual(_called_method(f"/api/v2/method/{name}", {}), name)
        self.assertEqual(_called_method("/api/method/frappe%2Edesk%2Eform%2Eload%2Egetdoc", {}), name)
        self.assertEqual(_called_method("/", {"cmd": name}), name)
        self.assertEqual(_called_method("/api/resource/HD Ticket", {}), "")

    def test_method_targets_lists_every_place_a_document_can_be_named(self):
        self.assertEqual(_method_targets({"doctype": "HD Ticket", "name": "1"}), [("HD Ticket", ["1"])])
        form = {"doctype": "ToDo", "name": "x", "args": '{"doctype": "HD Ticket", "name": "2"}'}
        self.assertIn(("HD Ticket", ["2"]), _method_targets(form))  # args wins in the handler, so it must be seen
        self.assertIn(("HD Ticket", ["3"]), _method_targets({"doc": {"doctype": "HD Ticket", "name": "3"}}))
        self.assertIn(("HD Ticket", ["4", "5"]), _method_targets({"doctype": "HD Ticket", "names": '["4", "5"]'}))
        self.assertEqual(_method_targets({}), [("", [])])
