import frappe
from frappe import _
from frappe.core.doctype.user_invitation.user_invitation import UserInvitation

AGENT_ROLES = {"Agent", "Agent Manager", "System Manager"}
# dimensy: one Email Template per audience, written by the site setup; without it Frappe's own email is sent
INVITATION_TEMPLATES = {"agent": "Undangan Petugas", "customer": "Undangan Pelanggan"}


class HelpdeskUserInvitation(UserInvitation):
    def _get_email_title(self):
        # Use the org's brand name (set during onboarding) in the invitation
        # subject — "You've been invited to join <brand> on Helpdesk" — falling
        # back to the framework app title when it isn't set. The override class
        # is registered site-wide, so invitations from other apps (ERPNext,
        # etc.) must keep their own app title.
        if self.app_name != "helpdesk":
            return super()._get_email_title()
        brand = frappe.db.get_single_value("HD Settings", "brand_name")
        if not brand:
            return super()._get_email_title()
        return _("{0} on {1}").format(brand, super()._get_email_title())

    def send_invitation_mail(self):
        template = self._invitation_template()
        if not template:
            return super().send_invitation_mail()
        # same key and link as UserInvitation.send_invitation_mail (Frappe 16.36.0); only the email differs
        key = frappe.generate_hash()
        self.db_set("key", frappe.utils.sha256_hash(key))
        invite_link = frappe.utils.get_url(
            f"/api/method/frappe.core.api.user_invitation.accept_invitation?key={key}"
        )
        mail = frappe.get_doc("Email Template", template).get_formatted_email(
            {"invite_link": invite_link, "email": self.email, "customer": self.get("customer")}
        )
        frappe.sendmail(
            recipients=self.email,
            subject=mail["subject"],
            content=mail["message"],
            with_container=True,
            now=True,
        )
        self.db_set("email_sent_at", frappe.utils.now())
        return key

    def _invitation_template(self) -> str | None:
        """Agents and customers get different invitation emails: "Portal Ticketing" means nothing to an agent."""
        if self.app_name != "helpdesk":
            return None
        audience = "agent" if {r.role for r in self.roles} & AGENT_ROLES else "customer"
        name = INVITATION_TEMPLATES[audience]
        return name if frappe.db.exists("Email Template", name) else None
