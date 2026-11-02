"""Read-only live audit. Private results stay in .verification-live; no cached GETs."""

from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import time

from bs4 import BeautifulSoup

from fad_downloader.domain import FadError, Limits, SUPPORTED_RESOURCE_KINDS, stable_url
from fad_downloader.env_config import read_credentials
from fad_downloader.exporter import export_bundle
from fad_downloader.moodle import Moodle
from fad_downloader.network import HttpClient
from fad_downloader.observability import configure
from fad_downloader.state import load_catalog


def local_digest(workspace, relative):
    base = workspace.resolve()
    target = workspace / relative
    if target.is_symlink() or not target.resolve().is_relative_to(base):
        raise ValueError("unsafe local path")
    digest, size = hashlib.sha256(), 0
    with target.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def remote_digest(http, url, budget):
    """Hash actual response bytes independently of Downloader and its validators."""
    start = time.monotonic()
    with http.request(url, headers={"Cache-Control": "no-cache"}) as response:
        if response.status_code != 200:
            raise ValueError("unexpected HTTP status")
        digest, size = hashlib.sha256(), 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            budget[0] += len(chunk)
            if (size > Limits().file_bytes or budget[0] > Limits().run_bytes
                    or time.monotonic() - start > Limits().request_seconds):
                raise ValueError("audit transfer limit")
            digest.update(chunk)
        length = response.headers.get("Content-Length")
        if length and not response.headers.get("Content-Encoding") and int(length) != size:
            raise ValueError("truncated response")
        return size, digest.hexdigest()


def normalized(text):
    return " ".join(text.split())


def semantic_checks(documents, exported, *, page=False):
    """Independent visible question/feedback text checks; no source HTML is printed."""
    target = normalized(BeautifulSoup(exported, "html.parser").get_text(" ", strip=True))
    checked, missing = 0, 0
    for content in documents:
        source = BeautifulSoup(content, "html.parser")
        selector = "#page-mod-page-view #region-main .generalbox" if page else ".qtext, .specificfeedback, .generalfeedback, .rightanswer"
        for node in source.select(selector):
            for hidden in node.select("script, style, [hidden], [aria-hidden='true'], input, select, textarea"):
                hidden.decompose()
            for text in node.stripped_strings:
                text = normalized(text)
                if text:
                    checked += 1
                    missing += int(text not in target)
    return checked, missing


def answer_markers(documents, exported):
    """Check explicit checked attributes against passive answer markers independently."""
    selected = unselected = 0
    seen = set()
    for content in documents:
        source = BeautifulSoup(content, "html.parser")
        for question in source.select(".que"):
            identity = question.get("id")
            if identity and identity in seen:
                continue
            seen.add(identity)
            for control in question.select('input[type="radio"], input[type="checkbox"]'):
                if control.find_parent(attrs={"hidden": True}) or control.has_attr("hidden"):
                    continue
                if control.has_attr("checked"):
                    selected += 1
                else:
                    unselected += 1
    text = BeautifulSoup(exported, "html.parser").get_text(" ", strip=True)
    return {"expected_selected": selected, "actual_selected": text.count("[selezionata]"),
            "expected_unselected": unselected, "actual_unselected": text.count("[non selezionata]")}


class RecordingClient:
    def __init__(self, client):
        self.client = client
        self.documents = []

    def document(self, *args, **kwargs):
        result = self.client.document(*args, **kwargs)
        self.documents.append(result[0])
        return result

    def __getattr__(self, name):
        return getattr(self.client, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exports-only", action="store_true", help="Use saved catalog and recheck HTML exports only")
    args = parser.parse_args()
    app = Path(__file__).resolve().parent
    candidates = [catalog.parents[2] for catalog in (app / ".verification-live").glob("*/workspace/.fad/catalog.json")]
    if not candidates:
        parser.error("Serve un precedente collaudo locale con catalogo e manifest.")
    run = max(candidates, key=lambda p: p.name)
    out = run / ("integrity-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    out.mkdir(mode=0o700)
    configure(enabled=False)
    moodle = Moodle(HttpClient())
    summary = {"stage": "login", "unconditional_remote_get": True,
               "catalog_rescanned": not args.exports_only}
    rows, budget = [], [0]

    def checkpoint():
        summary["remote_bytes"] = budget[0]
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (out / "details.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(json.dumps(summary), flush=True)

    try:
        username, password = read_credentials(app / ".env")
        account = moodle.login(username, password)
        password = None
        saved, _ = load_catalog(run / "workspace", account)
        records = {}
        workspaces = [run / "workspace"]
        workspaces += [p / "workspace" for p in sorted(run.glob("page-recheck-*"), key=lambda p: p.stat().st_mtime)]
        for workspace in workspaces:
            manifest = json.loads((workspace / ".fad/manifest.json").read_text(encoding="utf-8"))
            if manifest["account"] != account.key:
                raise ValueError("account mismatch")
            records.update({key: (workspace, record) for key, record in manifest["records"].items()})

        summary["stage"] = "saved_catalog_exports" if args.exports_only else "fresh_scan"
        checkpoint()
        fresh = saved if args.exports_only else moodle.scan(progress=lambda cat: print(json.dumps({"scan_resources": len(cat.resources)}), flush=True))
        old_ids, new_ids = {r.id for r in saved.resources}, {r.id for r in fresh.resources}
        selected = [r for r in fresh.resources if r.kind in SUPPORTED_RESOURCE_KINDS]
        if args.exports_only:
            selected = [r for r in selected if r.kind != "file"]
        summary.update(courses=len(fresh.courses), resources=len(fresh.resources),
                       kinds=dict(Counter(r.kind for r in fresh.resources)), scan_warnings=len(fresh.warnings),
                       catalog_added=len(new_ids - old_ids), catalog_removed=len(old_ids - new_ids),
                       supported_without_local=sum(r.id not in records for r in selected))
        rows.append({"catalog_added": sorted(new_ids - old_ids), "catalog_removed": sorted(old_ids - new_ids)})

        # Separate reference from Moodle API, without reusing activities()/expand().
        reference, reference_courses = set(), 0
        for course in ([] if args.exports_only else fresh.courses):
            sections = moodle.ajax("core_course_get_contents", {"courseid": course.id, "options": []})
            if not isinstance(sections, list):
                continue
            reference_courses += 1
            for section in sections:
                for module in section.get("modules", []):
                    for item in module.get("contents", []):
                        if item.get("type") == "file" and item.get("fileurl"):
                            reference.add(stable_url(item["fileurl"]))
        seen = {stable_url(r.url) for r in fresh.resources if r.kind == "file"}
        summary.update(reference_api_courses=reference_courses, reference_api_files=len(reference),
                       reference_api_coverage_complete=reference_courses == len(fresh.courses),
                       reference_files_not_in_catalog=len(reference - seen), stage="remote_hashes")
        checkpoint()
        counts = Counter()
        for index, resource in enumerate(selected, 1):
            row = {"id": resource.id, "kind": resource.kind}
            try:
                if resource.id not in records:
                    row["status"] = "missing_local"
                    counts[row["status"]] += 1
                    rows.append(row)
                    continue
                workspace, record = records[resource.id]
                local = local_digest(workspace, record["path"])
                row["local_manifest_matches"] = local == (record["size"], record["sha256"])
                counts["local_manifest_ok" if row["local_manifest_matches"] else "local_manifest_mismatch"] += 1
                if resource.kind == "file":
                    remote = remote_digest(moodle.http, resource.url, budget)
                    row.update(status="raw_equal" if remote == local else "raw_different",
                               remote_size=remote[0], local_size=local[0], remote_sha256=remote[1], local_sha256=local[1])
                    if resource.size is not None:
                        row["catalog_size_matches"] = resource.size == remote[0]
                        counts["catalog_size_ok" if row["catalog_size_matches"] else "catalog_size_mismatch"] += 1
                else:
                    client = RecordingClient(moodle.http)
                    assets = {Path(a["path"]).name: a for a in record.get("assets", [])}

                    def check_asset(url, name):
                        if name not in assets:
                            raise ValueError("new remote asset")
                        item = assets[name]
                        local_asset = local_digest(workspace, item["path"])
                        remote_asset = remote_digest(moodle.http, url, budget)
                        if local_asset != remote_asset:
                            raise ValueError("asset differs")
                        counts["asset_equal"] += 1
                        return name

                    regenerated = export_bundle(client, resource, check_asset)
                    row["status"] = "export_equal" if (len(regenerated), hashlib.sha256(regenerated).hexdigest()) == local else "export_different"
                    local_content = (workspace / record["path"]).read_bytes()
                    if row["status"] == "export_different":
                        before = BeautifulSoup(local_content, "html.parser")
                        after = BeautifulSoup(regenerated, "html.parser")
                        row["export_diff"] = {
                            "local_bytes": len(local_content), "remote_export_bytes": len(regenerated),
                            "same_title": before.title.get_text() == after.title.get_text(),
                            "same_visible_text": normalized(before.get_text(" ", strip=True)) == normalized(after.get_text(" ", strip=True)),
                        }
                        (out / ("private-export-" + resource.id + ".html")).write_bytes(regenerated)
                    checked, missing = semantic_checks(client.documents, local_content, page=resource.kind == "page")
                    row.update(semantic_text_checks=checked, semantic_text_missing=missing)
                    counts["semantic_text_checks"] += checked
                    counts["semantic_text_missing"] += missing
                    if resource.kind == "quiz_review":
                        markers = answer_markers(client.documents, local_content)
                        row["answer_markers"] = markers
                        counts["answer_marker_mismatch"] += int(
                            markers["expected_selected"] != markers["actual_selected"]
                            or markers["expected_unselected"] != markers["actual_unselected"]
                        )
                counts[row["status"]] += 1
            except Exception as exc:
                row.update(status="error", code=exc.code if isinstance(exc, FadError) else type(exc).__name__)
                counts["error"] += 1
            rows.append(row)
            summary["counts"] = dict(counts)
            if index % 10 == 0:
                checkpoint()
        summary.update(stage="complete", counts=dict(counts))
    except Exception as exc:
        summary.update(stage="failed", error_code=exc.code if isinstance(exc, FadError) else type(exc).__name__)
    finally:
        try:
            moodle.logout()
            summary["logout"] = "ok"
        except Exception:
            summary["logout"] = "failed_session_closed"
        checkpoint()
    failures = {"error", "raw_different", "export_different", "missing_local", "local_manifest_mismatch", "semantic_text_missing", "answer_marker_mismatch"}
    return int(summary["stage"] != "complete" or any(summary.get("counts", {}).get(k, 0) for k in failures))


if __name__ == "__main__":
    raise SystemExit(main())
