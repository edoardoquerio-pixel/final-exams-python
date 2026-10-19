"""Scoperta Moodle: API di lettura se disponibili, fallback HTML esplicito."""

import json
import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
from dataclasses import replace

from .domain import (
    Account,
    Catalog,
    Course,
    FadError,
    ORIGIN,
    Resource,
    Section,
    check_cancel,
    identifier,
    stable_url,
)
from .network import HttpClient, validate_url
from .observability import event, monitored


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
        self.sections = {}
        self.snap_complete = set()

    def close(self):
        self.http.close()
        self.account = None
        self.sesskey = None

    @monitored("auth.logout")
    def logout(self):
        try:
            if self.sesskey:
                from urllib.parse import urlencode

                self.http.document(
                    ORIGIN + "/login/logout.php?" + urlencode({"sesskey": self.sesskey}),
                    allow_logout=True,
                )
        finally:
            self.close()

    @monitored("auth.login")
    def login(self, username, password):
        raw, _ = self.http.document(ORIGIN + "/login/index.php")
        token = BeautifulSoup(raw, "html.parser").select_one('input[name="logintoken"]')
        if not token or not token.get("value"):
            raise FadError(
                "AUTH_REQUIRED", "Login non riconosciuto; SSO/MFA non supportato nella 0.0.1."
            )
        result, final = self.http.document(
            ORIGIN + "/login/index.php",
            "POST",
            data={
                "username": username,
                "password": password,
                "logintoken": token["value"],
                "anchor": "",
            },
        )
        posted = BeautifulSoup(result, "html.parser")
        if "/login/index.php" in urlsplit(final).path and posted.select_one(
            'input[name="logintoken"]'
        ):
            raise FadError(
                "AUTH_REQUIRED",
                "Login rifiutato dalla FAD: controllare username e password nel file .env o nei campi di accesso.",
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
        event("auth.accepted")
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
                if data[0].get("exception") in {
                    "require_login_exception",
                    "invalidsesskey",
                    "requireloginerror",
                }:
                    raise FadError("AUTH_REQUIRED", "Sessione scaduta durante la scansione.")
                if method == "core_get_fragment":
                    raise FadError("ACCESS_DENIED", "Frammento di sezione non disponibile.")
                self.unavailable.add(method)
                return None
            return data[0].get("data")
        except (ValueError, TypeError):
            self.unavailable.add(method)
            return None

    @monitored("scan.courses")
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
        event("scan.courses_result", courses=len(courses), partial=not complete)
        return list(courses.values())

    def resource(self, course, mid, name, kind, url, section="", size=None):
        identity = stable_url(url)
        if kind == "quiz_review":
            identity = parse_qs(urlsplit(url).query).get("attempt", [identity])[0]
        rid = identifier(f"{course.id}:{mid}:{kind}:{identity}")
        return Resource(
            rid, course.id, course.name, section or "Generale", mid, name, kind, url, size
        )

    def activities(self, course):
        found = {}
        data = self.ajax("core_course_get_contents", {"courseid": course.id, "options": []})
        if isinstance(data, list):
            for index, section in enumerate(data):
                number = int(section.get("section", index))
                self.sections[(course.id, number)] = Section(
                    str(number), course.id, section.get("name") or f"Sezione {number}", number
                )
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
                            raw_path = item.get("filepath", "/").strip("/")
                            if raw_path:
                                from .storage import clean_name

                                raw_path = "/".join(clean_name(p) for p in raw_path.split("/") if p)
                            r = replace(
                                r,
                                subfolder=raw_path,
                                section_index=int(section.get("section", index)),
                                activity_name=name,
                                section_id=str(number),
                            )
                            found[r.id] = r
                    elif url:
                        r = self.resource(course, mid, name, kind, url, sn)
                        r = replace(
                            r,
                            section_index=int(section.get("section", index)),
                            activity_name=name,
                            section_id=str(number),
                        )
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
            soup = self.snap_sections(course, soup)
            for node in soup.select(
                'li.section[id^="section-"], section.section[id^="section-"], [data-sectionid]'
            ):
                sid = re.fullmatch(r"section-(\d+)", node.get("id", ""))
                if sid:
                    index = int(sid.group(1))
                    title = node.select_one(".sectionname") or node.find(["h2", "h3"])
                    name = title.get_text(" ", strip=True) if title else f"Sezione {index}"
                    previous = self.sections.get((course.id, index))
                    self.sections[(course.id, index)] = Section(
                        str(index), course.id, previous.name if previous else name, index
                    )
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
                sid = re.fullmatch(r"section-(\d+)", parent.get("id", "")) if parent else None
                if sid:
                    index = int(sid.group(1))
                    section = self.sections.get((course.id, index))
                    r = replace(
                        r,
                        section=section.name if section else r.section,
                        section_index=index,
                        section_id=str(index),
                        activity_name=r.name,
                    )
                found[r.id] = r
            for link in file_links(soup, base):
                if any(stable_url(r.url) == stable_url(link) for r in found.values()):
                    continue
                name = unquote(urlsplit(link).path.rsplit("/", 1)[-1])
                r = self.resource(course, 0, name, "file", link)
                owner = next(
                    (
                        tag.find_parent("li", class_="section")
                        for tag in soup.select("a[href], object[data], embed[src], iframe[src]")
                        if urljoin(base, tag.get("href") or tag.get("data") or tag.get("src"))
                        == link
                    ),
                    None,
                )
                sid = re.fullmatch(r"section-(\d+)", owner.get("id", "")) if owner else None
                if sid:
                    index = int(sid.group(1))
                    section = self.sections.get((course.id, index))
                    if section:
                        r = replace(
                            r, section=section.name, section_id=section.id, section_index=index
                        )
                found[r.id] = r
        if not isinstance(data, list) and course.id not in self.snap_complete:
            self.warnings.append(
                f"Corso {course.id}: fallback HTML; contenuti dinamici non verificati."
            )
        return list(found.values())

    def snap_sections(self, course, soup):
        """Legge i frammenti del tema senza eseguire il JavaScript ricevuto."""
        scripts = "\n".join(tag.get_text() for tag in soup.select("script"))
        match = re.search(r"snapInit\s*\(\s*(\{[^\n]*?\})", scripts)
        if not match:
            return soup
        try:
            config = json.loads(match.group(1))
        except ValueError:
            self.warnings.append(f"Corso {course.id}: configurazione Snap non riconosciuta.")
            return soup
        if str(config.get("id")) != str(course.id):
            self.warnings.append(f"Corso {course.id}: configurazione Snap incoerente.")
            return soup
        expected = {}
        for link in soup.select(".chapters a[href], #chapters a[href], a.chapter-title[href]"):
            parsed = urlsplit(urljoin(course.url, link["href"]))
            if stable_url(urljoin(course.url, link["href"])) != stable_url(course.url):
                continue
            fragment = re.fullmatch(r"section-(\d+)", parsed.fragment)
            if fragment:
                number = int(fragment.group(1))
                expected[number] = link.get_text(" ", strip=True) or f"Sezione {number}"
                self.sections.setdefault(
                    (course.id, number), Section(str(number), course.id, expected[number], number)
                )
        if not config.get("partialrender"):
            return soup
        existing = {
            int(n["id"].split("-")[1])
            for n in soup.select('li.section[id^="section-"]')
            if re.fullmatch(r"section-\d+", n["id"])
        }
        fragments = []
        loaded = set(existing)
        attempts = 0
        limit = min(200, getattr(getattr(self.http, "limits", None), "pages", 10000))
        for number in sorted(expected):
            if number in existing:
                continue
            check_cancel(self.http.cancel)
            if attempts >= limit:
                self.warnings.append(f"Corso {course.id}: limite sezioni Snap raggiunto.")
                break
            attempts += 1
            try:
                result = self.ajax(
                    "core_get_fragment",
                    {
                        "component": "theme_snap",
                        "callback": "section",
                        "contextid": config.get("contextid"),
                        "args": [
                            {"name": "courseid", "value": str(course.id)},
                            {"name": "section", "value": str(number)},
                        ],
                    },
                )
                html = result.get("html") if isinstance(result, dict) else None
                if not isinstance(html, str):
                    raise FadError("UNSUPPORTED", "Frammento non disponibile.")
                fragment = soup_document(html, course.url)
                if not fragment.select_one(f'li.section[id="section-{number}"]'):
                    raise FadError("UNSUPPORTED", "Sezione non riconosciuta nel frammento.")
                for script in fragment.select("script"):
                    script.decompose()
                fragments.append(str(fragment))
                loaded.add(number)
            except FadError as exc:
                if exc.code in {"AUTH_REQUIRED", "CANCELLED"}:
                    raise
                section = self.sections[(course.id, number)]
                self.sections[(course.id, number)] = replace(section, available=False)
                self.warnings.append(
                    f"Corso {course.id}, sezione {number}: caricamento non riuscito."
                )
        for number in set(expected) - loaded:
            self.sections[(course.id, number)] = replace(
                self.sections[(course.id, number)], available=False
            )
        event(
            "scan.snap_sections",
            count=len(expected),
            resources=len(fragments),
            partial=bool(set(expected) - loaded),
        )
        if expected and set(expected).issubset(loaded):
            self.snap_complete.add(course.id)
        return BeautifulSoup(str(soup) + "\n" + "\n".join(fragments), "html.parser")

    def expand(self, course, resource):
        if resource.kind == "quiz":
            soup, base = self.page(resource.url)
            result = []
            for row in soup.select("table tr"):
                state = row.select_one(".state")
                table = row.find_parent("table")
                headers = table.select("thead tr th") if table else []
                if not headers and table:
                    header_row = table.find("tr")
                    headers = header_row.find_all("th", recursive=False) if header_row else []
                state_index = next((i for i, header in enumerate(headers)
                                    if header.get_text(" ", strip=True).casefold() in {"stato", "state", "status"}), None)
                cells = row.find_all("td", recursive=False)
                if state is None and state_index is not None and state_index < len(cells):
                    state = cells[state_index]
                if state is None and not headers:
                    state = row.select_one(".cell.c1")
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
                            replace(
                                self.resource(
                                    course,
                                    resource.activity_id,
                                    resource.name + " - tentativo " + attempt,
                                    "quiz_review",
                                    url,
                                    resource.section,
                                ),
                                activity_name=resource.activity_name or resource.name,
                                section_index=resource.section_index,
                                attempt_id=attempt,
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
                    replace(
                        self.resource(
                            course,
                            resource.activity_id,
                            unquote(urlsplit(url).path.rsplit("/", 1)[-1]),
                            "file",
                            url,
                            resource.section,
                        ),
                        activity_name=resource.activity_name or resource.name,
                        section_index=resource.section_index,
                        subfolder=self.folder_path(url) if resource.kind == "folder" else "",
                    )
                    for url in links
                ]
        return [resource]

    @staticmethod
    def folder_path(url):
        """pluginfile/context/mod_folder/content/revision/path/file."""
        from .storage import clean_name

        parts = unquote(urlsplit(url).path).split("/")
        if "mod_folder" not in parts:
            return ""
        index = parts.index("mod_folder")
        return "/".join(clean_name(p) for p in parts[index + 3 : -1] if p)

    @monitored("scan.catalog")
    def scan(self, emit=lambda text: None, progress=lambda catalog: None):
        self.warnings = []
        self.sections = {}
        self.snap_complete = set()
        catalog = Catalog(courses=self.courses())
        def publish():
            # Snapshot: the GUI must never iterate lists being mutated by this worker.
            progress(Catalog(
                courses=list(catalog.courses),
                resources=list(catalog.resources),
                sections=sorted(self.sections.values(), key=lambda s: (s.course_id, s.index)),
            ))

        publish()
        for index, course in enumerate(catalog.courses, 1):
            check_cancel(self.http.cancel)
            emit(f"Scansione corso {index}/{len(catalog.courses)}: " + course.name)
            try:
                for resource in self.activities(course):
                    try:
                        expanded = self.expand(course, resource)
                        catalog.resources.extend(
                            replace(
                                item,
                                section_id=item.section_id or resource.section_id,
                                section_index=resource.section_index,
                            )
                            for item in expanded
                        )
                    except FadError as exc:
                        if exc.code in {"CANCELLED", "AUTH_REQUIRED"}:
                            raise
                        self.warnings.append(f"{resource.name}: {exc}")
            except FadError as exc:
                if exc.code in {"CANCELLED", "AUTH_REQUIRED"}:
                    raise
                self.warnings.append(f"Corso {course.id}: {exc}")
            publish()
        catalog.resources = list({r.id: r for r in catalog.resources}.values())
        limit = getattr(getattr(self.http, "limits", None), "pages", 10000)
        if len(catalog.resources) > limit:
            catalog.resources = catalog.resources[:limit]
            self.warnings.append("Limite risorse raggiunto: scansione parziale.")
        catalog.warnings = list(self.warnings)
        catalog.sections = sorted(self.sections.values(), key=lambda s: (s.course_id, s.index))
        event(
            "scan.result",
            courses=len(catalog.courses),
            sections=len(catalog.sections),
            resources=len(catalog.resources),
            warnings=len(catalog.warnings),
            partial=bool(catalog.warnings),
        )
        return catalog
