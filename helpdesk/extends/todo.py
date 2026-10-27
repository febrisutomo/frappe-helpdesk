import frappe


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
    # any user can create a ToDo; only an agent (or the system) assigning a ticket may ring someone's bell.
    # Exception: the assignment rule runs in the customer's session while a portal ticket is being created.
    # HD Ticket.after_insert flags that request, which a customer cannot do from a separate ToDo insert.
    is_new_ticket_assignment = frappe.flags.get("hd_ticket_inserting") == doc.reference_name
    if (
        not is_new_ticket_assignment
        and frappe.session.user != "Administrator"
        and not frappe.db.exists("HD Agent", frappe.session.user)
    ):
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
