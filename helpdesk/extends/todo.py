import frappe
from frappe import _

from helpdesk.utils import (
    RESTRICTED_ASSIGNMENT_TEAMS,
    RESTRICTED_ASSIGNMENT_TYPE_PREFIXES,
    is_agent,
    is_ticket_auditor,
)


def validate(doc, method=None):
    """The ticketing administrator neither assigns tickets nor is assigned one.

    `frappe.desk.form.assign_to` only asks for read permission on the ticket, which the administrator has, and creates the ToDo
    without permission checks, so the rule is enforced here.
    """
    if doc.reference_type != "HD Ticket":
        return
    _check_direct_assignment(doc)
    if is_ticket_auditor() or (doc.allocated_to and is_ticket_auditor(doc.allocated_to)):
        frappe.throw(_("The ticketing administrator cannot assign tickets or be assigned one"), frappe.PermissionError)
    _check_restricted_assignee(doc)


def _check_direct_assignment(doc):
    """A ToDo made through the generic API (`/api/resource/ToDo`) is an assignment, and an assignment grants access to the ticket.

    `assign_to` and the assignment rules insert with ignore_permissions, so only a direct insert or edit reaches this check:
    it needs an agent who may already change the ticket, otherwise a customer or an agent of another team could give anyone,
    themselves included, a ticket they cannot reach.
    """
    if doc.flags.ignore_permissions or frappe.session.user == "Administrator":
        return
    if not (doc.is_new() or doc.has_value_changed("allocated_to") or doc.has_value_changed("reference_name")):
        return
    user = frappe.session.user
    if not is_agent(user) or not frappe.has_permission("HD Ticket", "write", doc.reference_name, user=user):
        frappe.throw(_("Not permitted"), frappe.PermissionError)


def _check_restricted_assignee(doc):
    """SRT and INS tickets go only to members of the Trusted Role teams.

    The assignment (and the access it grants) is what matters, so it is checked here for every way of assigning: the agent UI,
    `assign_to.add`, the assignment rules and server scripts. A cancelled ToDo or an unchanged assignee is not a new grant.
    """
    if not doc.allocated_to or doc.allocated_to == "Administrator" or doc.status == "Cancelled":
        return
    if not (doc.is_new() or doc.has_value_changed("allocated_to")):
        return
    ticket_type = frappe.db.get_value("HD Ticket", doc.reference_name, "ticket_type") or ""
    if not ticket_type.startswith(RESTRICTED_ASSIGNMENT_TYPE_PREFIXES):
        return
    if frappe.db.exists("HD Team Member", {"parent": ["in", RESTRICTED_ASSIGNMENT_TEAMS], "user": doc.allocated_to}):
        return
    frappe.throw(
        _("Only members of the RA Administrator, Security and Management teams can be assigned this type of ticket"),
        frappe.PermissionError,
    )


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
