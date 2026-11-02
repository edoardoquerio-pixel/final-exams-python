"""Classifica gli avvisi dell'ultimo collaudo reale senza stampare titoli o URL."""

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from pathlib import PurePosixPath
import secrets
import sys
from urllib.parse import parse_qs, urljoin, urlsplit

from fad_downloader.domain import FadError, Naming, ORIGIN, Resource
from fad_downloader.env_config import read_credentials
from fad_downloader.moodle import Moodle, file_links, soup_document
from fad_downloader.network import HttpClient
from fad_downloader.observability import configure, route_name
from fad_downloader.state import load_catalog
import fad_downloader.network as network


def main():
    app = Path(__file__).resolve().parent
    run = max((app / ".verification-live").iterdir(), key=lambda p: p.name)
    saved, _ = load_catalog(run / "workspace")
    suffixes = (": nessun allegato riconosciuto.", ": URL o azione non consentita dalla policy FAD.")
    targets = {w[:-len(suffix)] for w in saved.warnings for suffix in suffixes if w.endswith(suffix)}
    report = json.loads((run / "workspace/.fad/report.json").read_text(encoding="utf-8"))
    failed_ids = {r["resource_id"] for r in report["results"] if r["status"] not in {"scaricato", "aggiornato", "invariato"}}
    targets.update(r.name for r in saved.resources if r.id in failed_ids)
    configure(enabled=False)
    moodle = Moodle(HttpClient())
    results, rejections, private_targets = [], [], []
    original_validation = network.validate_url

    def validate(url, *args, **kwargs):
        try:
            return original_validation(url, *args, **kwargs)
        except FadError:
            rejections.append({"route": route_name(url), "same_origin": urlsplit(url).hostname == urlsplit(ORIGIN).hostname})
            raise

    network.validate_url = validate
    try:
        username, password = read_credentials(app / ".env")
        moodle.login(username, password)
        password = None
        cached = run / "private-diagnostic-resources.json"
        batches = [None] if "--cached" in sys.argv and cached.exists() else saved.courses
        visible_pages = {}
        for index, course in enumerate(batches, 1):
            try:
                resources = [Resource(**data) for data in json.loads(cached.read_text())] if course is None else moodle.activities(course)
                for resource in resources:
                    if resource.name not in targets:
                        continue
                    private_targets.append(asdict(resource))
                    result = {"kind": resource.kind}
                    try:
                        with moodle.http.request(resource.url) as response:
                            raw = b"".join(moodle.http.chunks(response, moodle.http.limits.document_bytes))
                            result["final_route"] = route_name(response.url)
                            result["document_bytes"] = len(raw)
                            result["html_content_type"] = "html" in response.headers.get("Content-Type", "").casefold()
                            extension = PurePosixPath(urlsplit(response.url).path).suffix.lower()
                            result["known_extension"] = extension if extension in {".php", ".html", ".htm", ".pdf", ".txt", ".zip", ".docx", ".mp4"} else "other"
                            result["pdf_magic"] = raw.startswith(b"%PDF-")
                            result["zip_magic"] = raw.startswith(b"PK\x03\x04")
                            soup = soup_document(raw, response.url)
                            result["resource_view_body"] = bool(soup.select_one("#page-mod-resource-view"))
                            candidates = [urljoin(response.url, tag.get("href") or tag.get("src") or tag.get("data"))
                                          for tag in soup.select("a[href], object[data], embed[src], iframe[src]")
                                          if "/pluginfile.php/" in (tag.get("href") or tag.get("src") or tag.get("data") or "")]
                            text = soup.get_text(" ", strip=True).casefold()
                            result["notification_nodes"] = len(soup.select(".alert, .notifyproblem, .notification, #notice"))
                            result["missing_file_marker"] = any(marker in text for marker in
                                                                 ("file not found", "resource file missing", "file non trovato", "file della risorsa non", "file richiesto non", "file mancante", "risorsa non contiene file", "file non esiste", "non è stato trovato il file"))
                            main = soup.select_one("#region-main") or soup
                            result["rendering"] = {selector: len(main.select(selector)) for selector in
                                                   (".resourcecontent", ".resourceworkaround", "iframe", "video", "audio", "object", "embed", "source", ".alert-danger", "[role=alert]")}
                            result["pluginfile_mentions"] = str(main).count("pluginfile.php")
                            result["frame_routes"] = [{"route": route_name(urljoin(response.url, tag["src"])),
                                                       "same_origin": urlsplit(urljoin(response.url, tag["src"])).hostname == urlsplit(ORIGIN).hostname}
                                                      for tag in main.select("iframe[src]")]
                            result.update(raw_file_references=len(candidates), accepted_file_links=len(file_links(soup, response.url)),
                                          folder_trees=len(soup.select(".foldertree")),
                                          empty_marker=any(marker in text for marker in ("no files", "nessun file", "cartella vuota", "non sono presenti file")))
                            media = [urljoin(response.url, tag["src"]) for tag in soup.select("video[src], audio[src], source[src]")
                                     if "/pluginfile.php/" in tag["src"]]
                            result["media_file_references"] = len(media)
                            result["internal_download_links"] = sum(
                                urlsplit(urljoin(response.url, tag["href"])).path == "/mod/resource/view.php"
                                and parse_qs(urlsplit(urljoin(response.url, tag["href"])).query).get("redirect") == ["1"]
                                for tag in soup.select("a[href]")
                            )
                            if resource.kind == "page":
                                selectors = ("#page-mod-page-view", "#region-main", "[role=main]", ".generalbox", ".resourcecontent",
                                             ".no-overflow", ".activity-description", ".snap-page-content", ".region-main-content")
                                result["page_selectors"] = {selector: len(soup.select(selector)) for selector in selectors}
                                result["generalbox_text_lengths"] = [len(n.get_text(" ", strip=True)) for n in soup.select(".generalbox")]
                                node = soup.select_one("#region-main .generalbox")
                                if node:
                                    visible_pages[resource.id] = " ".join(node.get_text(" ", strip=True).split())
                    except FadError as exc:
                        result["error_code"] = exc.code
                    results.append(result)
            except FadError as exc:
                results.append({"course_error_code": exc.code})
            print(json.dumps({"diagnostic_courses": index}), flush=True)
        summary = {"target_names": len(targets), "examined": len(results), "results": results,
                   "rejections": rejections, "kinds": dict(Counter(r.get("kind", "course") for r in results))}
        if "--export-pages" in sys.argv:
            from bs4 import BeautifulSoup
            from fad_downloader.database import Archive
            from fad_downloader.pdf_reports import export_user_report
            from fad_downloader.services import Downloader, plan, verify
            from fad_downloader.storage import SafeRoot, load_manifest

            destination = run / ("page-recheck-" + secrets.token_hex(4))
            archive = Archive(destination / "archive.sqlite3")
            secret = secrets.token_urlsafe(32)
            archive.register("collaudo_pagine", secret)
            session = archive.login("collaudo_pagine", secret)
            secret = None
            workspace = destination / "workspace"
            try:
                pages = [r for r in saved.resources if r.kind == "page"]
                report = Downloader(moodle.http, moodle.account, archive=archive, user_session=session).run(
                    plan(pages, workspace, moodle.account, Naming()), workspace)
                integrity = verify(workspace)
                manifest = load_manifest(SafeRoot(workspace), moodle.account)
                # Check private text in memory; only publish the boolean result.
                preserved = bool(visible_pages) and all(
                    resource_id in manifest["records"] and expected in " ".join(BeautifulSoup(
                        (workspace / manifest["records"][resource_id]["path"]).read_text(), "html.parser"
                    ).get_text(" ", strip=True).split()) for resource_id, expected in visible_pages.items()
                )
                export_user_report(archive, session, destination / "report.pdf")
                summary["page_recheck"] = {"counts": report["counts"], "checked": integrity["checked"],
                                           "issues": len(integrity["issues"]), "visible_text_preserved": preserved}
            finally:
                archive.logout(session)
        (run / "scan-diagnostics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (run / "private-diagnostic-resources.json").write_text(json.dumps(private_targets), encoding="utf-8")
        if "--brief" in sys.argv:
            print(json.dumps({"kinds": summary["kinds"], "page_recheck": summary.get("page_recheck"),
                              "final_routes": dict(Counter(r.get("final_route", r.get("error_code", "unknown")) for r in results)),
                              "missing_file_markers": sum(bool(r.get("missing_file_marker")) for r in results),
                              "resource_extensions": dict(Counter(r.get("known_extension", "unknown") for r in results if r.get("kind") == "resource")),
                              "resource_document_bytes": [r.get("document_bytes", 0) for r in results if r.get("kind") == "resource"]}), flush=True)
        else:
            print(json.dumps(summary), flush=True)
    finally:
        network.validate_url = original_validation
        try:
            moodle.logout()
        except Exception:
            moodle.close()


if __name__ == "__main__":
    main()
