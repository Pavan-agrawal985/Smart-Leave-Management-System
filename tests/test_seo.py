import json
import re
import xml.etree.ElementTree as ET

import pytest

PUBLIC = ["/", "/register", "/features", "/leave-management-for-banks",
          "/leave-management-for-corporate-offices", "/faq"]
PRIVATE = ["/login", "/forgot-password", "/health", "/verify/abc", "/invite/abc",
           "/reset-password/abc", "/owner/login", "/dashboard", "/admin/employees",
           "/leave/apply", "/reports/"]


def grab(html, pattern):
    match = re.search(pattern, html)
    assert match, pattern
    return match.group(1)


def title_of(html):
    return grab(html, r"<title>(.*?)</title>")


def description_of(html):
    return grab(html, r'<meta name="description" content="(.*?)">')


@pytest.mark.parametrize("url", PUBLIC)
def test_public_pages_have_the_seo_basics(client, url):
    r = client.get(url)
    assert r.status_code == 200
    html = r.data.decode()
    assert "X-Robots-Tag" not in r.headers                           # open to search engines
    assert html.count("<h1") == 1                                    # exactly one main heading
    assert f'<link rel="canonical" href="http://localhost{url}">' in html
    assert 10 <= len(title_of(html)) <= 65
    assert 50 <= len(description_of(html)) <= 160
    for tag in ('property="og:title"', 'property="og:description"', 'property="og:image"',
                'property="og:url"', 'name="twitter:card"'):
        assert tag in html
    assert "/static/og-image.png" in html


def test_every_public_page_has_its_own_title_and_description(client):
    titles, descriptions = [], []
    for url in PUBLIC:
        html = client.get(url).data.decode()
        titles.append(title_of(html))
        descriptions.append(description_of(html))
    assert len(set(titles)) == len(PUBLIC)
    assert len(set(descriptions)) == len(PUBLIC)


@pytest.mark.parametrize("url", PRIVATE)
def test_private_pages_stay_out_of_search_results(client, url):
    r = client.get(url)
    assert "noindex" in r.headers.get("X-Robots-Tag", "")


def test_content_pages_that_start_with_leave_are_not_hidden(client):
    r = client.get("/leave-management-for-banks")
    assert "X-Robots-Tag" not in r.headers                           # "/leave-..." is not "/leave/"


def test_sitemap_lists_the_public_pages_only(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200 and "xml" in r.mimetype
    root = ET.fromstring(r.data)
    urls = {el.text for el in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
    assert urls == {f"http://localhost{u}" for u in PUBLIC}


def test_robots_points_to_the_sitemap_and_blocks_private_areas(client):
    text = client.get("/robots.txt").data.decode()
    assert "Allow: /" in text and "Sitemap: http://localhost/sitemap.xml" in text
    for blocked in ("/admin/", "/owner/", "/leave/", "/reports/"):
        assert f"Disallow: {blocked}" in text


def test_landing_has_valid_structured_data(client):
    html = client.get("/").data.decode()
    data = json.loads(grab(html, r'<script type="application/ld\+json">(.*?)</script>'.replace(".*?", "(?s:.*?)")))
    assert data["@type"] == "SoftwareApplication" and data["name"] == "LeaveOk"
    assert data["url"] == "http://localhost/"


def test_share_image_and_caching(client):
    r = client.get("/static/og-image.png")
    assert r.status_code == 200 and r.mimetype == "image/png" and len(r.data) > 10000
    assert "max-age=604800" in client.get("/static/style.css").headers["Cache-Control"]


def test_footer_links_the_content_pages_everywhere(client):
    for url in ("/", "/login", "/faq"):
        html = client.get(url).data.decode()
        for target in ("/features", "/leave-management-for-banks",
                       "/leave-management-for-corporate-offices", "/faq"):
            assert f'href="{target}"' in html


def test_content_pages_say_the_right_things(client):
    banks = client.get("/leave-management-for-banks").data.decode()
    offices = client.get("/leave-management-for-corporate-offices").data.decode()
    assert "Privilege Leave" in banks and "Annual Leave" in offices
    for url in PUBLIC:
        text = client.get(url).data.decode().lower()
        assert "school" not in text and "college" not in text


def test_unknown_pages_are_a_real_404(client):
    assert client.get("/no-such-page").status_code == 404


def test_google_verification_tag_appears_only_when_configured(client, monkeypatch):
    assert "google-site-verification" not in client.get("/").data.decode()
    monkeypatch.setenv("GOOGLE_SITE_VERIFICATION", "abc123")
    assert '<meta name="google-site-verification" content="abc123">' in client.get("/").data.decode()