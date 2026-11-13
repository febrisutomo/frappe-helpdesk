import frappe
from frappe import _

from email.utils import parseaddr

from helpdesk.utils import can_reply_to_reporter, is_agent, is_internal_channel


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
    ticket_type, raised_by, channel = frappe.db.get_value("HD Ticket", doc.reference_name, ["ticket_type", "raised_by", "custom_channel"]) or ("", "", "")
    if is_internal_channel(channel):
        frappe.throw(_("An internal ticket is worked through internal comments, not replies."), frappe.PermissionError)
    if not can_reply_to_reporter(ticket_type, user, channel):
        frappe.throw(
            _("Only Customer Service writes to the reporter. Write the answer in an internal comment."),
            frappe.PermissionError,
        )
    # dimensy: the reply goes to the reporter recorded on the ticket only (a typo or a forged address would send the ticket's content to a
    # stranger), and nobody receives it in hiding: Cc stays visible to the reporter, Bcc is refused
    reporter = parseaddr(raised_by or "")[1].lower()
    recipients = {parseaddr(r)[1].lower() for r in (doc.recipients or "").replace(";", ",").split(",") if r.strip()}
    if recipients and recipients != {reporter}:
        frappe.throw(_("A reply goes to the reporter's email recorded on the ticket only."), frappe.PermissionError)
    if (doc.bcc or "").strip():
        frappe.throw(_("Bcc is not used on ticket replies."), frappe.PermissionError)
