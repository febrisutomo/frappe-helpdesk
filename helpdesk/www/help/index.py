import frappe
from bs4 import BeautifulSoup
from frappe.utils.html_utils import sanitize_html

# dimensy: public help center. Guests get only Published articles of Public
# categories; everything else is a 404. Read with get_all on purpose (guests
# have no role), the two filters below are the access rule.
no_cache = 1

PUBLIC = {"visibility": "Public"}


def get_context(context):
    parts = [p for p in (frappe.form_dict.get("app_path") or "").split("/") if p]
    context.no_header = 1
    context.logo = frappe.conf.get("helpdesk_help_logo") or ""
    context.source_code_url = frappe.conf.get("helpdesk_source_code_url") or ""
    context.categories = context.articles = context.article = context.category = None

    if not parts:
        context.title = "Pusat Bantuan"
        context.categories = categories()
    elif parts[0] == "articles" and len(parts) == 2:
        context.article = article(parts[1])
        context.title = context.article.title
    elif len(parts) == 1:
        context.category = frappe.db.get_value(
            "HD Article Category",
            {"name": parts[0], **PUBLIC},
            ["name", "category_name"],
            as_dict=True,
        ) or not_found()
        context.title = context.category.category_name
        context.articles = frappe.get_all(
            "HD Article",
            filters={"category": context.category.name, "status": "Published"},
            fields=["name", "title", "content"],
            order_by="idx asc, creation asc",
        )
        for a in context.articles:
            a.summary = BeautifulSoup(a.content or "", "html.parser").text.strip()[:140]
    else:
        not_found()
    return context


def not_found():
    raise frappe.DoesNotExistError


def categories():
    out = []
    for c in frappe.get_all(
        "HD Article Category",
        filters=PUBLIC,
        fields=["name", "category_name", "description"],
    ):
        c.count = frappe.db.count(
            "HD Article", {"category": c.name, "status": "Published"}
        )
        if c.count:
            out.append(c)
    return sorted(out, key=lambda c: c.category_name)


def article(name):
    a = frappe.db.get_value(
        "HD Article",
        {"name": name, "status": "Published"},
        ["name", "title", "content", "category", "modified"],
        as_dict=True,
    )
    if not a or not frappe.db.get_value(
        "HD Article Category", {"name": a.category, **PUBLIC}
    ):
        not_found()
    a.content = sanitize_html(a.content or "")
    a.category_name = frappe.db.get_value(
        "HD Article Category", a.category, "category_name"
    )
    return a
