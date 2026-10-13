import re

import frappe
from textblob import TextBlob
from textblob.exceptions import MissingCorpusError

from helpdesk.search import NUM_RESULTS
from helpdesk.utils import is_agent
from helpdesk.search import search as hd_search


def get_nouns(blob: TextBlob):
    try:
        return [word for word, pos in blob.pos_tags if pos[0] == "N"]
    except LookupError:
        return []


def get_noun_phrases(blob: TextBlob):
    try:
        return blob.noun_phrases
    except (LookupError, MissingCorpusError):
        return []


def search_with_enough_results(
    prev_res: list, query: str, qtype="and", public_only: bool = False
) -> tuple[list, bool]:
    out = hd_search(query, qtype=qtype)
    if not out:
        return prev_res, len(prev_res) == NUM_RESULTS
    items = prev_res + visible_items(out[0].get("items", []), public_only)
    items = list({v["id"]: v for v in items}.values())[:NUM_RESULTS]  # unique results
    return items, len(items) == NUM_RESULTS


def visible_items(items: list, public_only: bool = False) -> list:
    """dimensy: the index holds every Published article. Customers (and agents previewing the
    customer portal, `public_only`) only get articles of Public categories."""
    if is_agent() and not public_only:
        return items
    ids = {i["id"].split(":", 1)[1].split("#")[0] for i in items}
    if not ids:
        return []
    public = frappe.get_all("HD Article Category", filters={"visibility": "Public"}, pluck="name")
    allowed = set(
        frappe.get_all(
            "HD Article",
            filters={"name": ["in", list(ids)], "status": "Published", "category": ["in", public or [""]]},
            pluck="name",
        )
    )
    return [i for i in items if i["id"].split(":", 1)[1].split("#")[0] in allowed]


def sanitize_query(query: str) -> str:
    q = query.strip().lower()
    q = re.sub(r"[^a-z0-9\s]", " ", q)
    # Collapse multiple spaces into one
    q = re.sub(r"\s+", " ", q)
    return q.strip()


@frappe.whitelist()
def get_article_stats(article_name: str):
    frappe.has_permission("HD Article", doc=article_name, throw=True)
    views = frappe.db.get_value("HD Article", article_name, "views")

    likes = frappe.db.count(
        "HD Article Feedback",
        filters={
            "article": article_name,
            "feedback": 1,
        },
    )

    dislikes = frappe.db.count(
        "HD Article Feedback",
        filters={
            "article": article_name,
            "feedback": 2,
        },
    )

    return {
        "views": views,
        "likes": likes,
        "dislikes": dislikes,
    }


@frappe.whitelist()
def search(query: str, public_only: bool = False) -> list:
    public_only = bool(int(public_only)) if str(public_only).isdigit() else str(public_only).lower() == "true"
    query = sanitize_query(query)
    ret, enough = search_with_enough_results([], query, public_only=public_only)
    if enough:
        return ret
    blob = TextBlob(query)  # fallback
    if noun_phrases := get_noun_phrases(blob):
        query = " ".join(noun_phrases)
        ret, enough = search_with_enough_results(ret, query, public_only=public_only)
        if enough:
            return ret
        ret, enough = search_with_enough_results(ret, query, qtype="or", public_only=public_only)
        if enough:
            return ret
    if nouns := get_nouns(blob):
        query = " ".join(nouns)
        ret, enough = search_with_enough_results(ret, query, public_only=public_only)
        if enough:
            return ret
        ret, enough = search_with_enough_results(ret, query, qtype="or", public_only=public_only)
    return ret
