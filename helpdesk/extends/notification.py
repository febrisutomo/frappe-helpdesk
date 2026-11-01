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
    """A notification is read, changed and deleted by its recipient only; creating one for someone else (an @mention) is left
    to the role permissions.

    The recipient is read from the database, not from `doc`: on a write the document in memory already carries the values the
    request sent, so an agent could make a notification its own by changing `user_to` in the same request.
    """
    user = user or frappe.session.user
    if ptype == "create":
        return True
    if user == "Administrator":
        return True
    recipient = doc.get("user_to") if doc.is_new() else frappe.db.get_value("HD Notification", doc.name, "user_to")
    return recipient == user
