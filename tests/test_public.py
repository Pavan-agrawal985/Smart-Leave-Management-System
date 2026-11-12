def test_landing_page_for_visitors(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Create your organization" in r.data
    assert b'name="description"' in r.data


def test_logged_in_user_skips_landing(login_as, world):
    r = login_as("emp@alpha.io").get("/")
    assert r.status_code == 302 and "/dashboard" in r.headers["Location"]


def test_robots_and_sitemap(client):
    robots = client.get("/robots.txt")
    assert b"Disallow: /admin/" in robots.data and b"sitemap.xml" in robots.data
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200 and b"/register" in sitemap.data