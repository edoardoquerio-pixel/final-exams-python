"""Scoperta Moodle: API di lettura se disponibili, fallback HTML esplicito."""

import json
import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

from .domain import (
    Account,
    Catalog,
    Course,
    FadError,
    ORIGIN,
    Resource,
    check_cancel,
    identifier,
    stable_url,
)
from .network import HttpClient, validate_url


def soup_document(content, url):
    soup = BeautifulSoup(content, "html.parser")
    if "/login/" in urlsplit(url).path or soup.select_one('input[name="logintoken"]'):
        raise FadError("AUTH_REQUIRED", "Sessione scaduta: accedere nuovamente e ritentare.")
    if soup.select_one('.errorbox, [data-rel="fatalerror"]'):
        raise FadError("ACCESS_DENIED", "Moodle ha restituito una pagina di errore.")
    return soup


def file_links(soup, base):
    links = {}
    for tag in soup.select("a[href], object[data], embed[src], iframe[src]"):
        raw = tag.get("href") or tag.get("data") or tag.get("src")
        url = urljoin(base, raw)
        if "/pluginfile.php/" in urlsplit(url).path:
            try:
                validate_url(url)
            except FadError:
                continue
            links[stable_url(url)] = url
    return list(links.values())


class Moodle:
    def __init__(self, http: HttpClient):
        self.http = http
        self.account = None
        self.sesskey = None
        self.unavailable = set()
        self.warnings = []

    def close(self):
        self.http.close()
        self.account = None
        self.sesskey = None

    def login(self, username, password):
        raw, _ = self.http.document(ORIGIN + "/login/index.php")
        token = BeautifulSoup(raw, "html.parser").select_one('input[name="logintoken"]')
        if not token or not token.get("value"):
            raise FadError(
                "AUTH_REQUIRED", "Login non riconosciuto; SSO/MFA non supportato nella 0.0.1."
            )
        self.http.document(
            ORIGIN + "/login/index.php",
            "POST",
            data={
                "username": username,
                "password": password,
                "logintoken": token["value"],
                "anchor": "",
            },
        )
        raw, final = self.http.document(ORIGIN + "/my/")
        soup = soup_document(raw, final)
        if not soup.select_one('a[href*="/login/logout.php"]'):
            raise FadError("AUTH_REQUIRED", "Accesso non confermato. Controllare le credenziali.")
        match = re.search(r'["\']sesskey["\']\s*:\s*["\']([^"\']+)', str(soup))
        self.sesskey = match.group(1) if match else None
        match = re.search(r'["\']userid["\']\s*:\s*(\d+)', str(soup))
        profile = soup.select_one(
            '.usermenu a[href*="/user/profile.php"], .usermenu a[href*="/user/view.php"]'
        )
        uid = match.group(1) if match else None
        if not uid and profile:
            uid = parse_qs(urlsplit(profile["href"]).query).get("id", [None])[0]
        if not uid:
            self.warnings.append(
                "ID utente non esposto dal tema: workspace associato allo username confermato dal login."
            )
            uid = "username:" + username.strip().casefold()
        self.account = Account(ORIGIN, uid)
        return self.account

    def page(self, url):
        content, final = self.http.document(url)
        return soup_document(content, final), final

    def ajax(self, method, args):
        if not self.sesskey or method in self.unavailable:
            return None
        try:
            content, final = self.http.document(
                ORIGIN + "/lib/ajax/service.php?sesskey=" + self.sesskey,
                "POST",
                json=[{"index": 0, "methodname": method, "args": args}],
            )
            if "/login/" in final:
                raise FadError("AUTH_REQUIRED", "Sessione scaduta.")
            data = json.loads(content)
            if not isinstance(data, list) or not data or not isinstance(data[0], dict):
                raise ValueError
            if data[0].get("error"):
                self.unavailable.add(method)
                return None
            return data[0].get("data")
        except (ValueError, TypeError):
            self.unavailable.add(method)
            return None

    def courses(self):
        courses = {}
        complete = False
        for offset in range(0, 10000, 100):
            check_cancel(self.http.cancel)
            data = self.ajax(
                "core_course_get_enrolled_courses_by_timeline_classification",
                {"offset": offset, "limit": 100, "classification": "all", "sort": "fullname"},
            )
            if not isinstance(data, dict) or not isinstance(data.get("courses"), list):
                break
            batch = data["courses"]
            before = len(courses)
            for item in batch:
                cid = int(item["id"])
                courses[cid] = Course(
                    cid, item.get("fullname", str(cid)), f"{ORIGIN}/course/view.php?id={cid}"
                )
            if len(batch) < 100:
                complete = True
                break
            if len(courses) == before:
                break
        if not complete:
            self.warnings.append(
                "Elenco corsi da dashboard: completezza non garantita senza API paginata."
            )
            soup, base = self.page(ORIGIN + "/my/")
            for a in soup.select("a[href]"):
                url = urljoin(base, a["href"])
                parts = urlsplit(url)
                cid = parse_qs(parts.query).get("id", [""])[0]
                if parts.path == "/course/view.php" and cid.isdigit():
                    courses.setdefault(
                        int(cid), Course(int(cid), a.get_text(" ", strip=True) or cid, url)
                    )
        return list(courses.values())

    def resource(self, course, mid, name, kind, url, section="", size=None):
        rid = identifier(f"{course.id}:{mid}:{kind}:{stable_url(url)}")
        return Resource(
            rid, course.id, course.name, section or "Generale", mid, name, kind, url, size
        )

    def activities(self, course):
        found = {}
        data = self.ajax("core_course_get_contents", {"courseid": course.id, "options": []})
        if isinstance(data, list):
            for section in data:
                for mod in section.get("modules", []):
                    mid, kind = int(mod["id"]), mod.get("modname", "unknown")
                    name, url = mod.get("name", str(mid)), mod.get("url", "")
                    sn = section.get("name", "Generale")
                    contents = [
                        c
                        for c in mod.get("contents", [])
                        if c.get("type") == "file" and c.get("fileurl")
                    ]
                    if kind in {"folder", "resource"} and contents:
                        for item in contents:
                            r = self.resource(
                                course,
                                mid,
                                item.get("filename", "file"),
                                "file",
                                item["fileurl"],
                                sn,
                                item.get("filesize"),
                            )
                            found[r.id] = r
                    elif url:
                        r = self.resource(course, mid, name, kind, url, sn)
                        found[r.id] = r
        covered = {r.activity_id for r in found.values()}
        pending, visited = [course.url], set()
        while pending:
            if len(visited) >= 200:
                self.warnings.append(f"Corso {course.id}: limite sezioni raggiunto.")
                break
            url = pending.pop(0)
            if stable_url(url) in visited:
                continue
            visited.add(stable_url(url))
            soup, base = self.page(url)
            for a in soup.select("a[href]"):
                link = urljoin(base, a["href"])
                parts, query = urlsplit(link), parse_qs(urlsplit(link).query)
                cid = query.get("id", [""])[0]
                if (
                    parts.path == "/course/view.php"
                    and cid == str(course.id)
                    and ("section" in query or "sectionid" in query)
                ):
                    try:
                        validate_url(link)
                    except FadError:
                        continue
                    if stable_url(link) not in visited:
                        pending.append(link)
                match = re.fullmatch(r"/mod/(\w+)/view\.php", parts.path)
                if not match or not cid.isdigit() or int(cid) in covered:
                    continue
                mid = int(cid)
                covered.add(mid)
                parent = a.find_parent(attrs={"data-sectionid": True}) or a.find_parent(
                    "li", class_="section"
                )
                title = parent.find(["h2", "h3"]) if parent else None
                r = self.resource(
                    course,
                    mid,
                    a.get_text(" ", strip=True) or cid,
                    match[1],
                    link,
                    title.get_text(" ", strip=True) if title else "Generale",
                )
                found[r.id] = r
            for link in file_links(soup, base):
                if any(stable_url(r.url) == stable_url(link) for r in found.values()):
                    continue
                name = unquote(urlsplit(link).path.rsplit("/", 1)[-1])
                r = self.resource(course, 0, name, "file", link)
                found[r.id] = r
        if not isinstance(data, list):
            self.warnings.append(
                f"Corso {course.id}: fallback HTML; contenuti dinamici non verificati."
            )
        return list(found.values())

    def expand(self, course, resource):
        if resource.kind == "quiz":
            soup, base = self.page(resource.url)
            result = []
            for row in soup.select("table tr"):
                state = row.select_one(".state, .cell.c1")
                text = state.get_text(" ", strip=True).casefold() if state else ""
                if not any(
                    word in text for word in ("finished", "terminato", "completato", "concluso")
                ):
                    continue
                link = row.select_one('a[href*="/mod/quiz/review.php"]')
                if link:
                    url = urljoin(base, link["href"])
                    attempt = parse_qs(urlsplit(url).query).get("attempt", [""])[0]
                    if attempt.isdigit():
                        result.append(
                            self.resource(
                                course,
                                resource.activity_id,
                                resource.name + " - tentativo " + attempt,
                                "quiz_review",
                                url,
                                resource.section,
                            )
                        )
            if not result:
                self.warnings.append(
                    f"{resource.name}: nessun tentativo completato e revisionabile riconosciuto."
                )
            return result
        if resource.kind in {"folder", "resource"}:
            with self.http.request(resource.url) as response:
                if "html" not in response.headers.get("Content-Type", "").lower():
                    return [
                        self.resource(
                            course,
                            resource.activity_id,
                            resource.name,
                            "file",
                            response.url,
                            resource.section,
                        )
                    ]
                raw = b"".join(self.http.chunks(response, 20 * 1024**2))
                soup = soup_document(raw, response.url)
                links = file_links(soup, response.url)
                if not links:
                    self.warnings.append(f"{resource.name}: nessun allegato riconosciuto.")
                return [
                    self.resource(
                        course,
                        resource.activity_id,
                        unquote(urlsplit(url).path.rsplit("/", 1)[-1]),
                        "file",
                        url,
                        resource.section,
                    )
                    for url in links
                ]
        return [resource]

    def scan(self, emit=lambda text: None):
        self.warnings = []
        catalog = Catalog(courses=self.courses())
        for course in catalog.courses:
            check_cancel(self.http.cancel)
            emit("Scansione: " + course.name)
            try:
                for resource in self.activities(course):
                    try:
                        catalog.resources.extend(self.expand(course, resource))
                    except FadError as exc:
                        if exc.code in {"CANCELLED", "AUTH_REQUIRED"}:
                            raise
                        self.warnings.append(f"{resource.name}: {exc}")
            except FadError as exc:
                if exc.code in {"CANCELLED", "AUTH_REQUIRED"}:
                    raise
                self.warnings.append(f"Corso {course.id}: {exc}")
        catalog.resources = list({r.id: r for r in catalog.resources}.values())
        catalog.warnings = list(self.warnings)
        return catalog
