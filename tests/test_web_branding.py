from tests.conftest import auth_get


def test_logo_and_favicon_are_served_as_svg(client):
    for path in ("/web/logo.svg", "/web/favicon.svg"):
        response = auth_get(client, path)

        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith("image/svg+xml"), path
        assert response.text.lstrip().startswith("<svg"), path


def test_brand_assets_need_auth(client):
    for path in ("/web/logo.svg", "/web/favicon.svg"):
        assert client.get(path).status_code == 401, path


def test_page_links_the_favicon_and_shows_the_logo(client):
    html = auth_get(client, "/web").text

    assert '<link rel="icon" type="image/svg+xml" href="/web/favicon.svg">' in html
    assert 'class="brand-t"' in html
    assert ">Syncer<" in html
    assert 'class="brand-logo"' not in html


def test_brand_links_to_the_github_repository(client):
    html = auth_get(client, "/web").text
    anchor = html.split('class="brand"', 1)[1].split(">", 1)[0]

    assert 'href="https://github.com/romi477/t-syncer"' in anchor
    assert 'target="_blank"' in anchor
    assert "noopener" in anchor


def test_sidebar_offers_the_swagger_docs_in_a_new_tab(client):
    html = auth_get(client, "/web").text
    anchor = html.split('data-field="swagger-link"', 1)[1].split(">", 1)[0]

    assert 'href="/docs"' in anchor
    assert 'target="_blank"' in anchor
    assert "noopener" in anchor


def test_swagger_target_requires_auth(client):
    assert client.get("/docs").status_code == 401
