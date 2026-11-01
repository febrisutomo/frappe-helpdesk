import frappe


def permission_query(user: str | None = None):
    """Everyone reads only the notifications addressed to them.

    dimensy: the role permissions of HD Notification have no per-user scope, so any agent could list every other agent's
    notifications (ticket numbers included) through the generic API.
    """
    user = user or frappe.session.user
    if user == "Administrator":
        return
    return "`tabHD Notification`.`user_to` = {u}".format(u=frappe.db.escape(user))


def has_permission(doc, ptype=None, user=None):
    """Reading, changing or deleting a notification is for its recipient; creating one for someone else (an @mention) is not limited
    here, role permissions decide that."""
    user = user or frappe.session.user
    if ptype not in ("read", "write", "delete"):
        return True
    return user == "Administrator" or doc.get("user_to") == user
