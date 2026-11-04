import frappe
from frappe import _

from helpdesk.utils import can_reply_to_reporter, is_agent


def before_insert(doc, method=None):
    """One door to the reporter: an agent's outgoing reply on a ticket is accepted only from Customer Service.

    Every way of replying ends in a Communication (the reply box, bulk reply, `email.make`, a direct insert), so the rule is checked
    here. RA Administrator may also write to the applicant of a revocation ticket (authentication). Customers' own messages are
    received, not sent, and the system acts as Administrator.
    """
    if doc.reference_doctype != "HD Ticket" or doc.sent_or_received != "Sent" or doc.communication_type != "Communication":
        return
    user = frappe.session.user
    if user in ("Administrator", "Guest") or not is_agent(user):
        return
    if can_reply_to_reporter(frappe.db.get_value("HD Ticket", doc.reference_name, "ticket_type"), user):
        return
    frappe.throw(
        _("Only Customer Service writes to the reporter. Write the answer in an internal comment."),
        frappe.PermissionError,
    )
