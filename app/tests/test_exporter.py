from dataclasses import replace

from bs4 import BeautifulSoup
import pytest

from fad_downloader.demo import DemoHttp, catalog
from fad_downloader.domain import FadError
from fad_downloader.exporter import export_bundle, static_answers


def test_static_answers_preserve_visible_fields():
    soup = BeautifulSoup(
        """<input type="hidden" value="SECRET">
        <input type="checkbox" checked><input value="Visible answer">
        <textarea>Long answer</textarea><select><option>A</option><option selected>B</option></select>
        <div hidden>HIDDEN</div><span style="display: none">INVISIBLE</span>""",
        "html.parser",
    )
    html = str(static_answers(soup))
    for value in ("[selezionata]", "Visible answer", "Long answer", "B"):
        assert value in html
    for value in ("SECRET", "HIDDEN", "INVISIBLE", "<input", "<select"):
        assert value not in html


def test_html_sanitized_and_remote_assets_removed():
    http = DemoHttp()
    markup = b"""<div class="resourcecontent"><script>alert(1)</script><p onclick="bad()">Hello</p>
      <img src="https://evil.test/tracker.png" onerror="bad()"><a href="javascript:alert(1)">Link</a>
      <iframe src="https://evil.test"></iframe><svg onload="bad()"></svg></div>"""
    http.document = lambda url: (markup, url)
    output = export_bundle(http, catalog().resources[1], lambda u, n: n).decode()
    for forbidden in (
        "<script",
        "onclick",
        "onerror",
        "javascript:",
        "evil.test",
        "<iframe",
        "<svg",
    ):
        assert forbidden not in output
    assert "Hello" in output


def test_quiz_unknown_type_fails_closed():
    http = DemoHttp()
    http.document = lambda url: (b'<div class="que custom-plugin">Unknown</div>', url)
    with pytest.raises(FadError, match="Tipo di domanda"):
        export_bundle(http, catalog().resources[2], lambda u, n: n)


def test_html_attachment_body_uses_sanitizer_and_has_no_moodle_fallback():
    from fad_downloader.domain import ORIGIN
    http = DemoHttp()
    resource = replace(catalog().resources[1], url=ORIGIN+'/pluginfile.php/1/mod_resource/content/1/lesson.html')
    markup = b'<html><head><script>HEAD_SECRET</script></head><body><h1>Lesson body</h1><div class="resourcecontent">Inner part</div><script>BAD_SCRIPT</script><p onclick="bad()">Example</p><iframe src="https://evil.test"></iframe></body></html>'
    http.document = lambda url: (markup, url)
    html = export_bundle(http, resource, lambda u,n:n).decode()
    assert 'Lesson body' in html and 'Example' in html and 'Inner part' in html
    assert all(x not in html for x in ('HEAD_SECRET','BAD_SCRIPT','onclick','<iframe','evil.test'))
    http.document = lambda url: (b'<html><body>Unrecognized Moodle layout</body></html>', url)
    with pytest.raises(FadError, match='Contenuto HTML'):
        export_bundle(http, replace(resource, url=ORIGIN+'/mod/page/view.php?id=1'), lambda u,n:n)


def test_page_without_overflow_wrapper_exports_only_module_content():
    http = DemoHttp()
    http.document = lambda url: (
        b'<body id="page-mod-page-view"><nav>PRIVATE_NAV</nav><main id="region-main">'
        b'<div class="generalbox"><p>Plain page content</p><script>BAD_SCRIPT</script></div>'
        b'<footer>OTHER_CONTENT</footer></main></body>', url,
    )
    html = export_bundle(http, catalog().resources[1], lambda u, n: n).decode()
    assert "Plain page content" in html
    for excluded in ("PRIVATE_NAV", "OTHER_CONTENT", "BAD_SCRIPT", "<script"):
        assert excluded not in html


def test_page_fallback_does_not_export_an_unrecognized_page_region():
    http = DemoHttp()
    http.document = lambda url: (
        b'<body id="page-course-view"><main id="region-main"><div class="generalbox">'
        b'Unrelated course content</div></main></body>', url,
    )
    with pytest.raises(FadError, match="non riconosciuto"):
        export_bundle(http, catalog().resources[1], lambda u, n: n)


def test_asset_links_rewritten():
    http = DemoHttp()
    http.document = lambda url: (
        b'<div class="resourcecontent"><img src="/pluginfile.php/1/content/a.png"></div>',
        url,
    )
    written = []

    def save(url, name):
        written.append((url, name))
        return name

    html = export_bundle(http, catalog().resources[1], save).decode()
    assert len(written) == 1
    assert "assets/" + written[0][1] in html
    assert "/pluginfile.php/" not in html


def test_quiz_pagination_only_same_attempt():
    http = DemoHttp()

    def document(url):
        if "page=1" in url:
            return b'<div class="que shortanswer"><input value="Second"></div>', url
        return (
            b'<div class="que shortanswer"><input value="First"></div><div class="paging"><a href="/mod/quiz/review.php?attempt=1&page=1">Next</a><a href="/mod/quiz/review.php?attempt=99">Other</a></div>',
            url,
        )

    http.document = document
    html = export_bundle(http, replace(catalog().resources[2]), lambda u, n: n).decode()
    assert "First" in html and "Second" in html
