import functools
import json
import re
from urllib.parse import unquote

import frappe
import phonenumbers
from bs4 import BeautifulSoup
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.realtime import get_website_room
from frappe.utils import floor
from frappe.utils.safe_exec import get_safe_globals
from frappe.utils.telemetry import capture as _capture
from phonenumbers import NumberParseException
from phonenumbers import PhoneNumberFormat as PNF
from pypika.functions import Replace


def check_permissions(doctype, parent, doc=None):
    user = frappe.session.user

    permissions = ("select", "read")
    has_select_permission, has_read_permission = [
        frappe.has_permission(doctype, perm, user=user, doc=doc, parent_doctype=parent)
        for perm in permissions
    ]

    if not has_select_permission and not has_read_permission:
        frappe.throw(
            _("Insufficient Permission for {0}").format(doctype), frappe.PermissionError
        )


def is_admin(user: str = None) -> bool:
    """
    Check whether `user` is an admin

    :param user: User to check against, defaults to current user
    :return: Whether `user` is an admin
    """
    user = user or frappe.session.user
    return user == "Administrator"


def is_agent(user: str | None = None) -> bool:
    """
    Check whether `user` is an agent

    :param user: User to check against, defaults to current user
    :return: Whether `user` is an agent
    """
    user = user or frappe.session.user
    roles = frappe.get_roles(user)
    return (
        is_admin()
        # dimensy: a System Manager configures Helpdesk like Administrator does; without a team or
        # HD Agent record it still sees no tickets and gets no assignments
        or "System Manager" in roles
        or "Agent Manager" in roles
        or "Agent" in roles
        or bool(frappe.db.exists("HD Agent", {"name": user}))
    )


# Dimensy: internal ticket data that must never reach non-agents (portal customers).
INTERNAL_TICKET_FIELDS = (
    "priority",
    "agent_group",
    "sla",
    "agreement_status",
    "response_by",
    "resolution_by",
    "service_level_agreement_creation",
    "on_hold_since",
    "total_hold_time",
    "first_response_time",
    "first_responded_on",
    "avg_response_time",
    "resolution_date",
    "resolution_time",
    "user_resolution_time",
    "first_response_failed_by",
    "resolution_failed_by",
    "last_agent_response",
    "_assign",
    "_seen",
    "_liked_by",
    "_comments",  # copy of the replies, contains agent emails
    "ticket_type",  # internal classification (e.g. security incident)
)


_SAFE_COUNT = re.compile(r"^count\((\*|name)\)( as \w+)?$")


def _plain_field_name(expression: str) -> str | None:
    """Reduce a client-supplied field expression to a bare field name, or None if it is not one.

    Handles aliases ("priority as p"), table prefixes ("`tabHD Ticket`.priority") and case.
    """
    name = re.split(r"\s+as\s+", str(expression).strip(), flags=re.IGNORECASE)[0]
    name = name.replace("`", "").strip().lower()
    if name.startswith("tabhd ticket."):
        name = name[len("tabhd ticket.") :]
    return name if re.fullmatch(r"[a-z_][a-z0-9_]*", name) else None


def is_internal_ticket_field(fieldname: str | None) -> bool:
    """Whether a ticket field expression must be withheld from non-agents.

    Custom fields count as internal: they are added for agents (channel, platform, contact email) and
    a field meant for customers has to be exposed deliberately, not by default. Anything that is not a
    bare field name (functions, sub-queries, aliases hiding one) is treated as internal.
    """
    if not fieldname:
        return False
    if _SAFE_COUNT.match(str(fieldname).strip().lower()):
        return False
    name = _plain_field_name(fieldname)
    return name is None or name in INTERNAL_TICKET_FIELDS or name.startswith("custom_")


def _strings_in(value) -> list[str]:
    """Every string in an already decoded filter structure (keys and values, any depth)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [t for k, v in value.items() for t in _strings_in(k) + _strings_in(v)]
    if isinstance(value, (list, tuple)):
        return [t for v in value for t in _strings_in(v)]
    return []


def _mentions_internal_ticket_field(value) -> bool:
    """Whether a filter, `order_by` or `group_by` refers to an internal ticket field.

    Works on the decoded structure, because that is what Frappe executes: JSON escapes such as
    "\\u0070riority" are decoded first, so a raw-text scan cannot be bypassed that way.
    """
    if isinstance(value, str) and value.strip()[:1] in ("[", "{"):
        try:
            value = json.loads(value)
        except ValueError:
            pass  # not JSON: treated as plain text below
    for text in _strings_in(value):
        for term in re.split(r"[,\s]+", text.lower()):
            term = term.strip("()`\"'")
            if term in ("", "asc", "desc"):
                continue
            if "." in term:  # `tabHD Ticket`.priority
                term = term.rsplit(".", 1)[1].strip("`\"'")
            if term in INTERNAL_TICKET_FIELDS or term.startswith("custom_"):
                return True
    return False


def _is_set_value_call(path: str, form) -> bool:
    """True only when the request runs frappe.client.set_value, read the way Frappe reads the method name."""
    if form.get("cmd") not in (None, "frappe.client.set_value"):
        return False
    for prefix in ("/api/method/", "/api/v2/method/"):
        if path.startswith(prefix):
            return unquote(path[len(prefix) :]).rstrip("/") == "frappe.client.set_value"
    return False


def _is_plain_value(value) -> bool:
    """A value to store, not a field reference: scalars only, and never the name of an internal field."""
    if value is None or isinstance(value, (int, float)):
        return True
    if not isinstance(value, str):
        return False
    name = _plain_field_name(value)
    return not (name and (name in INTERNAL_TICKET_FIELDS or name.startswith("custom_")))


def restrict_internal_ticket_access():
    """`before_request` hook: customers cannot ask the generic Frappe API for internal ticket data.

    Field-level permissions hide the regular fields, but Frappe always includes `_assign` and `_comments`
    and lets clients filter and sort by any readable column. For non-agents querying HD Ticket this drops
    internal fields from `fields`/`fieldname` and refuses filters, ordering and grouping on them.
    """
    user = frappe.session.user
    if user in ("Administrator", "Guest") or not getattr(frappe.local, "request", None) or is_agent(user):
        return
    form = frappe.local.form_dict
    path = frappe.local.request.path or ""
    doctype = form.get("doctype")
    for prefix in ("/api/resource/", "/api/v2/document/", "/api/v2/doctype/"):  # REST v1 and v2 name the doctype in the path
        if path.startswith(prefix):
            doctype = unquote(path[len(prefix) :].split("/")[0])
    if str(doctype or "").strip().lower() != "hd ticket":
        return

    # every parameter that names the columns to return (get_list uses `pluck`, reportview `field`)
    for key in ("fields", "fieldname", "field", "pluck", "group_by_field"):
        value = form.get(key)
        if value is None:
            continue
        parsed = frappe.parse_json(value) if isinstance(value, str) and value.strip()[:1] in "[{" else value
        if isinstance(parsed, list):
            form[key] = json.dumps([f for f in parsed if isinstance(f, str) and not is_internal_ticket_field(f)])
        elif (
            isinstance(parsed, dict)
            and key == "fieldname"
            and _is_set_value_call(path, form)
            and all(_is_plain_value(v) for v in parsed.values())
        ):
            # set_value with several fields at once (the portal closes a ticket with its feedback this way).
            # Only there: read endpoints treat a dict as SQL functions, e.g. {"MAX": "priority"}.
            kept = {k: v for k, v in parsed.items() if isinstance(k, str) and not is_internal_ticket_field(k)}
            form[key] = json.dumps(kept) if kept else "name"
        elif not isinstance(parsed, str) or is_internal_ticket_field(parsed):
            form[key] = "name"  # internal field, or a shape we cannot vet (e.g. a JSON object): fail closed
    for key in ("filters", "or_filters", "order_by", "group_by"):
        value = form.get(key)
        if value and _mentions_internal_ticket_field(value):
            frappe.throw(_("Not permitted"), frappe.PermissionError)


def get_customer_agent_label() -> str:
    """Sender name shown to customers for agent replies (site config `helpdesk_customer_agent_name`)."""
    return frappe.conf.get("helpdesk_customer_agent_name") or "Support Team"


def get_agent_name(user: str = None) -> str | None:
    """
    Get the HD Agent name for `user`

    The HD Agent's name is the user (see HD Agent controller), so this
    returns the user when an agent record exists, else None.

    :param user: User to check against, defaults to current user
    :return: HD Agent name, or None if `user` is not an agent
    """
    user = user or frappe.session.user
    return user if frappe.db.exists("HD Agent", user) else None


def publish_event(
    event: str,
    room: str | None = None,
    data: dict | None = None,
    user: str | None = None,
):
    """
    Publish `event` to a room with `data`

    :param event: Event name. Example: "refetch_resource"
    :param data: Data to be sent with the event
    :param user: User to send the event to, defaults to current user
    """
    room = room or get_website_room()
    user = user or frappe.session.user
    frappe.publish_realtime(
        event, message=data, room=room, after_commit=True, user=user
    )


def get_doc_room(doctype: str, name: str) -> str:
    return f"open_doc:{doctype}/{name}"


def capture_event(event: str):
    return _capture(event, "helpdesk")


def get_customers(user: str = "", contact: str = "", get_roles=False):
    """
    Get `Customer` from `Contact`

    :param contact: Contact which belongs to a customer
    :param user: User to check against, defaults to current user
    :return: Customer `name` if available
    """
    user = user or frappe.session.user
    if not contact:
        contact = frappe.db.get_value("Contact", {"user": user})

    HDCustomer = frappe.qb.DocType("HD Customer")
    HDCustomerMember = frappe.qb.DocType("HD Customer Member")

    query = (
        frappe.qb.from_(HDCustomerMember)
        .where(HDCustomerMember.contact_name == contact)
        .join(HDCustomer)
        .on(HDCustomer.name == HDCustomerMember.parent)
        .select(HDCustomer.name, HDCustomerMember.is_manager)
        .distinct()
    ).run(as_dict=True)
    customers = [d.get("name") for d in query]
    if get_roles:
        customers = [
            {"name": d.get("name"), "is_manager": d.get("is_manager")} for d in query
        ]

    return tuple(customers)


def extract_mentions(html):
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    mentions = []
    for d in soup.find_all("span", attrs={"data-type": "mention"}):
        mentions.append(
            frappe._dict(full_name=d.get("data-label"), email=d.get("data-id"))
        )
    return mentions


def alphanumeric_to_int(s: str) -> int | None:
    """
    Get int from alphanumeric string, using regex
    String example: "foo-123" -> 123


    :param s: Alphanumeric string to be searched for
    :return: Integer if a number is found
    """
    s = re.search(r"\d+", s)

    if not s:
        return

    return int(s.group(0))


def get_context(d: Document) -> dict:
    """
    Get safe context for `safe_eval`

    :param doc: `Document` to add in context
    :return: Context with `doc` and safe variables
    """
    utils = get_safe_globals().get("frappe").get("utils")
    return {
        "doc": d.as_dict(),
        "frappe": frappe._dict(utils=utils),
    }


def agent_only(fn):
    """Decorator to validate if user is an agent."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_agent():
            frappe.throw(
                msg=_("You are not permitted to access this resource."),
                title=_("Not Allowed"),
                exc=frappe.PermissionError,
            )

        return fn(*args, **kwargs)

    return wrapper


def is_agent_manager(user: str | None = None) -> bool:
    """
    Check whether `user` may manage other agents

    :param user: User to check against, defaults to current user
    :return: Whether `user` is an agent manager, system manager or admin
    """
    roles = set(frappe.get_roles(user))
    return bool(roles & {"Administrator", "System Manager", "Agent Manager"})


def agent_manager_only(fn):
    """Decorator to validate if user is an agent manager."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_agent_manager():
            frappe.throw(
                msg=_("You are not permitted to access this resource."),
                title=_("Not Allowed"),
                exc=frappe.PermissionError,
            )

        return fn(*args, **kwargs)

    return wrapper


def get_agents_team(user: str | None = None):
    """Teams the user belongs to. Defaults to the session user."""
    user = user or frappe.session.user
    Team = frappe.qb.DocType("HD Team")
    TeamMember = frappe.qb.DocType("HD Team Member")

    teams = (
        frappe.qb.from_(TeamMember)
        .join(Team)
        .on(Team.name == TeamMember.parent)
        .where(TeamMember.user == user)
        .where(Team.disabled == 0)
        .select(Team.team_name, Team.ignore_restrictions)
        .run(as_dict=True)
    )
    return teams


contact_default_columns = [
    {
        "label": "Name",
        "type": "Data",
        "key": "full_name",
        "width": "17rem",
    },
    {
        "label": "Email",
        "type": "Data",
        "key": "email_id",
        "width": "17rem",
    },
    {
        "label": "Mobile",
        "type": "Data",
        "key": "mobile_no",
        "width": "12rem",
    },
    {
        "label": "Created On",
        "type": "Datetime",
        "key": "creation",
        "width": "8rem",
    },
]

contact_default_rows = ["name", "email_id", "mobile_no", "image", "creation"]

call_log_default_columns = [
    {
        "label": "Name",
        "type": "Data",
        "key": "name",
        "width": "9rem",
    },
    {
        "label": "Caller",
        "type": "Link",
        "key": "caller",
        "options": "User",
        "width": "12rem",
    },
    {
        "label": "Receiver",
        "type": "Link",
        "key": "receiver",
        "options": "User",
        "width": "12rem",
    },
    {
        "label": "Type",
        "type": "Select",
        "key": "type",
        "width": "9rem",
    },
    {
        "label": "Medium",
        "type": "Select",
        "key": "telephony_medium",
        "width": "9rem",
    },
    {
        "label": "Status",
        "type": "Select",
        "key": "status",
        "width": "9rem",
    },
    {
        "label": "Duration",
        "type": "Duration",
        "key": "duration",
        "width": "6rem",
    },
    {
        "label": "From (number)",
        "type": "Data",
        "key": "from",
        "width": "9rem",
    },
    {
        "label": "To (number)",
        "type": "Data",
        "key": "to",
        "width": "9rem",
    },
    {
        "label": "Created On",
        "type": "Datetime",
        "key": "creation",
        "width": "8rem",
    },
]


def seconds_to_duration(seconds):
    if not seconds:
        return "0s"

    hours = floor(seconds // 3600)
    minutes = floor((seconds % 3600) // 60)
    seconds = floor((seconds % 3600) % 60)

    # 1h 0m 0s -> 1h
    # 0h 1m 0s -> 1m
    # 0h 0m 1s -> 1s
    # 1h 1m 0s -> 1h 1m
    # 1h 0m 1s -> 1h 1s
    # 0h 1m 1s -> 1m 1s
    # 1h 1m 1s -> 1h 1m 1s

    if hours and minutes and seconds:
        return f"{hours}h {minutes}m {seconds}s"
    elif hours and minutes:
        return f"{hours}h {minutes}m"
    elif hours and seconds:
        return f"{hours}h {seconds}s"
    elif minutes and seconds:
        return f"{minutes}m {seconds}s"
    elif hours:
        return f"{hours}h"
    elif minutes:
        return f"{minutes}m"
    elif seconds:
        return f"{seconds}s"
    else:
        return "0s"


def parse_phone_number(phone_number, default_country="IN"):
    try:
        # Parse the number
        number = phonenumbers.parse(phone_number, default_country)

        # Get various information about the number
        result = {
            "is_valid": phonenumbers.is_valid_number(number),
            "country_code": number.country_code,
            "national_number": str(number.national_number),
            "formats": {
                "international": phonenumbers.format_number(number, PNF.INTERNATIONAL),
                "national": phonenumbers.format_number(number, PNF.NATIONAL),
                "E164": phonenumbers.format_number(number, PNF.E164),
                "RFC3966": phonenumbers.format_number(number, PNF.RFC3966),
            },
            "type": phonenumbers.number_type(number),
            "country": phonenumbers.region_code_for_number(number),
            "is_possible": phonenumbers.is_possible_number(number),
        }

        return {"success": True, **result}
    except NumberParseException as e:
        return {"success": False, "error": str(e)}


def get_contact(phone_number):
    if not phone_number:
        return {"mobile_no": phone_number}

    cleaned_number = (
        phone_number.strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
        .replace("+", "")
    )

    # Check if the number is associated with a contact
    Contact = frappe.qb.DocType("Contact")
    normalized_phone = Replace(
        Replace(
            Replace(Replace(Replace(Contact.phone, " ", ""), "-", ""), "(", ""), ")", ""
        ),
        "+",
        "",
    )
    query = (
        frappe.qb.from_(Contact)
        .select(Contact.name, Contact.full_name, Contact.image, Contact.phone)
        .where(normalized_phone.like(f"%{cleaned_number}%"))
        .orderby("modified", order=Order.desc)
    )
    contacts = query.run(as_dict=True)
    return contacts[0] if contacts else {"mobile_no": phone_number}


def get_contact_by_phone_number(phone_number):
    """Get contact by phone number."""
    number = parse_phone_number(phone_number)
    if number.get("is_valid"):
        return get_contact(number.get("national_number"))
    else:
        return get_contact(phone_number)


def parse_call_log(call):
    call["show_recording"] = False
    call["_duration"] = seconds_to_duration(call.get("duration"))
    if call.get("type") == "Incoming":
        call["activity_type"] = "incoming_call"
        contact = get_contact_by_phone_number(call.get("from"))
        receiver = (
            frappe.db.get_values(
                "User", call.get("receiver"), ["full_name", "user_image"]
            )[0]
            if call.get("receiver")
            else [None, None]
        )
        call["_caller"] = {
            "label": contact.get("full_name", "Unknown"),
            "image": contact.get("image"),
        }
        call["_receiver"] = {
            "label": receiver[0] or "Unknown",
            "image": receiver[1] or "",
        }
    elif call.get("type") == "Outgoing":
        call["activity_type"] = "outgoing_call"
        contact = get_contact_by_phone_number(call.get("to"))
        caller = (
            frappe.db.get_values(
                "User", call.get("caller"), ["full_name", "user_image"]
            )[0]
            if call.get("caller")
            else [None, None]
        )
        call["_caller"] = {
            "label": caller[0] or "Unknown",
            "image": caller[1] or "",
        }
        call["_receiver"] = {
            "label": contact.get("full_name", "Unknown"),
            "image": contact.get("image"),
        }

    return call


def parse_call_logs(calls):
    return [parse_call_log(call) for call in calls] if calls else []


def is_json_valid(json_string):
    try:
        json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False


def is_frappe_version(version: str, above: bool = False, below: bool = False):
    from frappe.pulse.utils import get_frappe_version

    current_version = get_frappe_version()
    major_version = int(current_version.split(".")[0])
    target_version = int(version.split(".")[0])

    if above:
        return major_version >= target_version
    if below:
        return major_version < target_version
    return major_version == target_version


def format_time_difference(dt, context="ago"):
    if not dt:
        return ""
    now = frappe.utils.now_datetime()
    if isinstance(dt, str):
        dt = frappe.utils.get_datetime(dt)

    if context == "until":
        diff = dt - now
        past_label = "overdue"
    else:
        diff = now - dt
        past_label = "0m"

    total_seconds = diff.total_seconds()

    if total_seconds < 0:
        return past_label

    if total_seconds < 3600:
        return f"{int(total_seconds // 60)}m"
    elif total_seconds < 86400:
        return f"{int(total_seconds // 3600)}h"
    else:
        return f"{int(total_seconds // 86400)}d"


def get_country_from_timezone(time_zone: str):
    country = frappe.db.get_value(
        "Country", {"time_zones": ["like", f"%{time_zone}%"]}, "name"
    )
    return country or None


def strip_internal_ticket_fields(response=None, request=None):
    """after_request hook (dimensy P17): remove internal ticket fields from JSON responses for non-agents.

    P10/P11 vet what customers ask for, but endpoints that save a document answer with the whole
    document: frappe.client.set_value (used by the customer portal itself), save, insert, run_doc_method
    and savedocs return every field of the ticket. Filtering the response covers all of them, including
    endpoints added later. Only JSON bodies that mention an HD Ticket are parsed.
    """
    if response is None or frappe.session.user in ("Administrator", "Guest") or is_agent():
        return
    if "json" not in (response.content_type or "") or b'"HD Ticket"' not in response.get_data():
        return
    try:
        data = json.loads(response.get_data())
    except ValueError:
        return

    def scrub(value):
        if isinstance(value, dict):
            if value.get("doctype") == "HD Ticket":
                for key in [k for k in value if is_internal_ticket_field(k)]:
                    del value[key]
            for item in value.values():
                scrub(item)
        elif isinstance(value, list):
            for item in value:
                scrub(item)

    scrub(data)
    from frappe.utils.response import json_handler

    response.set_data(json.dumps(data, default=json_handler, separators=(",", ":")))
