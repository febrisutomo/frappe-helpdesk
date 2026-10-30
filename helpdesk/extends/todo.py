import frappe
from frappe import _

from helpdesk.utils import is_ticket_auditor


def validate(doc, method=None):
    """The ticketing administrator neither assigns tickets nor is assigned one.

    `frappe.desk.form.assign_to` only asks for read permission on the ticket, which the administrator has, and creates the ToDo
    without permission checks, so the rule is enforced here.
    """
    if doc.reference_type != "HD Ticket":
        return
    if is_ticket_auditor() or (doc.allocated_to and is_ticket_auditor(doc.allocated_to)):
        frappe.throw(_("The ticketing administrator cannot assign tickets or be assigned one"), frappe.PermissionError)


def after_insert(doc, method=None):
    """Bell notice for the agent a ticket is assigned to.

    Helpdesk only created it in HD Ticket.assign_agent, which the agent UI and the assignment rules do not use
    (they call frappe.desk.form.assign_to), so assignments were announced by email only.
    """
    if (
        doc.reference_type != "HD Ticket"
        or not doc.allocated_to
        or doc.allocated_to == frappe.session.user
        or not frappe.db.exists("HD Agent", doc.allocated_to)
        or not frappe.db.exists("HD Ticket", doc.reference_name)
    ):
        return
    # any user can create a ToDo; only an agent (or the system) assigning a ticket may ring someone's bell
    if frappe.session.user != "Administrator" and not frappe.db.exists("HD Agent", frappe.session.user):
        return
    frappe.get_doc(
        {
            "doctype": "HD Notification",
            "user_from": frappe.session.user,
            "user_to": doc.allocated_to,
            "reference_ticket": doc.reference_name,
            "notification_type": "Assignment",
        }
    ).insert(ignore_permissions=True)
