import re

import frappe
from bs4 import BeautifulSoup
from frappe.utils import getdate
from frappe.utils.html_utils import sanitize_html

# dimensy: public help center. Guests get only Published articles of Public
# categories; everything else is a 404. Read with get_all on purpose (guests
# have no role), the two filters below are the access rule.
no_cache = 1

PUBLIC = {"visibility": "Public"}
PUBLISHED = {"status": "Published"}
LABELS = {"General": "Informasi Umum"}  # "General" is a reserved category name
MONTHS = "Januari Februari Maret April Mei Juni Juli Agustus September Oktober November Desember".split()


def get_context(context):
    parts = [p for p in (frappe.form_dict.get("app_path") or "").split("/") if p]
    context.no_header = 1
    context.logo = frappe.conf.get("helpdesk_help_logo") or ""
    context.categories = context.articles = context.article = context.category = None

    if not parts:
        context.title = "Pusat Bantuan"
        context.categories = categories()
        names = {c.name: c.label for c in context.categories}
        # titles for the client-side quick search on the home page
        context.index = frappe.get_all(
            "HD Article",
            filters={**PUBLISHED, "category": ["in", list(names) or [""]]},
            fields=["name", "title", "category"],
            order_by="title asc",
        )
        for a in context.index:
            a.category_label = names[a.category]
    elif parts[0] == "articles" and len(parts) == 2:
        context.article = article(parts[1])
        context.title = context.article.title
    elif len(parts) == 1:
        c = frappe.db.get_value(
            "HD Article Category",
            {"name": parts[0], **PUBLIC},
            ["name", "category_name", "description"],
            as_dict=True,
        ) or not_found()
        c.label = LABELS.get(c.category_name, c.category_name)
        context.category = c
        context.title = c.label
        context.articles = frappe.get_all(
            "HD Article",
            filters={"category": c.name, **PUBLISHED},
            fields=["name", "title", "content"],
            order_by="idx asc, creation asc",
        )
        for a in context.articles:
            soup = BeautifulSoup(a.content or "", "html.parser")
            for table in soup("table"):
                table.decompose()
            text = re.sub(r"\s+([.,;:)])", r"\1", soup.get_text(" ")).strip()
            text = re.sub(r"\s+", " ", text)
            a.summary = text[:160] + ("…" if len(text) > 160 else "")
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
        c.count = frappe.db.count("HD Article", {"category": c.name, **PUBLISHED})
        c.label = LABELS.get(c.category_name, c.category_name)
        if c.count:
            out.append(c)
    # General first, then alphabetical regardless of case ("e-Meterai")
    return sorted(out, key=lambda c: (c.category_name != "General", c.label.lower()))


def article(name):
    a = frappe.db.get_value(
        "HD Article",
        {"name": name, **PUBLISHED},
        ["name", "title", "content", "category", "modified"],
        as_dict=True,
    )
    if not a or not frappe.db.get_value(
        "HD Article Category", {"name": a.category, **PUBLIC}
    ):
        not_found()
    a.content = sanitize_html(a.content or "")
    category_name = frappe.db.get_value(
        "HD Article Category", a.category, "category_name"
    )
    a.category_label = LABELS.get(category_name, category_name)
    d = getdate(a.modified)
    a.updated = f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    return a
