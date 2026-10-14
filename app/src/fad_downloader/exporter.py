"""Esportazioni passive: prima risposte statiche, poi sanitizzazione nh3."""

from html import escape
from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
import nh3

from .domain import FadError, identifier, stable_url
from .moodle import soup_document

TAGS = {
    "p",
    "div",
    "span",
    "h1",
    "h2",
    "h3",
    "h4",
    "ul",
    "ol",
    "li",
    "br",
    "hr",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "pre",
    "code",
    "blockquote",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "img",
    "a",
    "sub",
    "sup",
}


def static_answers(soup):
    for tag in list(
        soup.select('[hidden], [aria-hidden="true"], input[type="hidden"], script, style')
    ):
        tag.decompose()
    for tag in list(soup.select("[style]")):
        style = tag.get("style", "").replace(" ", "").casefold()
        if "display:none" in style or "visibility:hidden" in style:
            tag.decompose()
    for tag in list(soup.select("input, textarea, select")):
        kind = tag.get("type", "text").lower()
        if kind in {"submit", "button", "reset", "password", "file", "image"}:
            tag.decompose()
            continue
        if tag.name == "select":
            value = (
                ", ".join(o.get_text(" ", strip=True) for o in tag.select("option[selected]"))
                or "(nessuna selezione visibile)"
            )
        elif tag.name == "textarea":
            value = tag.get_text()
        elif kind in {"checkbox", "radio"}:
            value = "[selezionata] " if tag.has_attr("checked") else "[non selezionata] "
        else:
            value = tag.get("value", "")
        replacement = soup.new_tag("span")
        replacement.string = value
        tag.replace_with(replacement)
    return soup


def html_page(title, body):
    return (
        "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        "img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        f"<title>{escape(title)}</title><style>body{{font:16px sans-serif;max-width:1000px;margin:2em auto;padding:1em}}"
        "img{max-width:100%}table{border-collapse:collapse}td,th{padding:.5em;border:1px solid #ccc}"
        f"</style></head><body><h1>{escape(title)}</h1>{body}</body></html>"
    ).encode()


def export_bundle(client, resource, write_asset):
    """write_asset(url, name) salva un asset nella generazione; errori impediscono il commit."""
    url = resource.url
    if resource.kind == "book":
        parts = urlsplit(url)
        mid = parse_qs(parts.query).get("id", [""])[0]
        url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                "/mod/book/tool/print/index.php",
                urlencode({"id": mid}),
                "",
            )
        )
    fragments, visited, pending = [], set(), [url]
    while pending:
        current = pending.pop(0)
        if stable_url(current) in visited:
            continue
        if len(visited) >= 100:
            raise FadError("LIMIT", "Troppe pagine di revisione.")
        visited.add(stable_url(current))
        content, final = client.document(current)
        soup = soup_document(content, final)
        if resource.kind == "quiz_review":
            nodes = soup.select(".que, .quizreviewsummary, .quizattemptsummary")
            if not soup.select(".que"):
                raise FadError("UNSUPPORTED", "Revisione quiz senza domande visibili riconosciute.")
            allowed_types = {
                "multichoice",
                "truefalse",
                "shortanswer",
                "numerical",
                "essay",
                "match",
                "description",
            }
            for question in soup.select(".que"):
                classes = set(question.get("class", []))
                if not classes.intersection(allowed_types):
                    raise FadError(
                        "UNSUPPORTED",
                        "Tipo di domanda non supportato: export sospeso per non perdere risposte.",
                    )
            attempt = parse_qs(urlsplit(resource.url).query).get("attempt")
            for a in soup.select(".paging a[href], .pagination a[href], .othernav a[href]"):
                link = urljoin(final, a["href"])
                if (
                    urlsplit(link).path == "/mod/quiz/review.php"
                    and parse_qs(urlsplit(link).query).get("attempt") == attempt
                ):
                    pending.append(link)
        elif resource.kind == "book":
            nodes = soup.select(".book_content")
        else:
            nodes = soup.select(
                ".resourcecontent, #region-main .generalbox .no-overflow, .activity-description .no-overflow"
            )
        if not nodes:
            raise FadError("UNSUPPORTED", "Contenuto HTML non riconosciuto nel tema Moodle.")
        # Copia i frammenti per non alterare il DOM mentre si cercano pagine successive.
        fragment = static_answers(BeautifulSoup("\n".join(str(n) for n in nodes), "html.parser"))
        for tag in fragment.select("img, a"):
            attr = "src" if tag.name == "img" else "href"
            raw = tag.get(attr, "")
            if raw.startswith("#"):
                continue
            target = urljoin(final, raw)
            if "/pluginfile.php/" in urlsplit(target).path:
                suffix = PurePosixPath(urlsplit(target).path).suffix.lower()
                if tag.name == "img" and suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                    tag.replace_with("[immagine non esportabile]")
                    continue
                name = identifier(stable_url(target))[:20] + suffix[:12]
                tag[attr] = "assets/" + write_asset(target, name)
            else:
                # Nessun URL remoto con token o caricamento implicito nell'export.
                if tag.name == "img":
                    tag.replace_with("[immagine esterna non inclusa]")
                else:
                    tag.attrs.pop("href", None)
        fragments.append(
            nh3.clean(
                str(fragment),
                tags=TAGS,
                attributes={
                    "a": {"href"},
                    "img": {"src", "alt"},
                    "td": {"colspan", "rowspan"},
                    "th": {"colspan", "rowspan"},
                },
                clean_content_tags={"script", "style", "iframe", "object", "embed", "svg"},
                url_schemes=set(),
            )
        )
    return html_page(resource.name, "\n".join(fragments))
