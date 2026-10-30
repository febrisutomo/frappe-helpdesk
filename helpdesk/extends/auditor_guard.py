"""Limits of the ticketing administrator (role Admin Ticketing, see `helpdesk.utils.is_ticket_auditor`).

The role manages accounts, teams and ticket types, which would also let it make itself an agent, join the Security team,
change another account's password or hide incident tickets by renaming their type. These guards close those ways around
the rule that the administrator reads tickets (except incidents) but never works on them. Any other user is unaffected.
"""

import frappe
from frappe import _

from helpdesk.utils import AUDITOR_HIDDEN_TYPE_PREFIX, is_ticket_auditor


def _refuse(message: str):
    frappe.throw(message, frappe.PermissionError)


def validate_user(doc, method=None):
    """Runs in before_validate: `User.validate` moves `new_password` aside, so a later hook would not see it."""
    if not is_ticket_auditor():
        return
    me = frappe.session.user
    before = doc.get_doc_before_save()
    if doc.name == me and before and {r.role for r in doc.roles} != {r.role for r in before.roles}:
        _refuse(_("The ticketing administrator cannot change its own roles"))
    if doc.get("new_password") and doc.name != me:
        _refuse(_("The ticketing administrator cannot set the password of another account; use the password reset link"))


def validate_team(doc, method=None):
    if is_ticket_auditor() and any(row.user == frappe.session.user for row in doc.get("users") or []):
        _refuse(_("The ticketing administrator cannot be a member of a team"))


def validate_agent(doc, method=None):
    if is_ticket_auditor() and doc.name == frappe.session.user:
        _refuse(_("The ticketing administrator cannot be an agent"))


def before_rename_ticket_type(doc, method=None, old=None, new=None, merge=False):
    if is_ticket_auditor() and (old or doc.name).startswith(AUDITOR_HIDDEN_TYPE_PREFIX):
        _refuse(_("The ticketing administrator cannot rename a security incident ticket type"))


def on_trash_ticket_type(doc, method=None):
    if is_ticket_auditor() and doc.name.startswith(AUDITOR_HIDDEN_TYPE_PREFIX):
        _refuse(_("The ticketing administrator cannot delete a security incident ticket type"))
