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
