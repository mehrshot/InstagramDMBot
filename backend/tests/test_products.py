import io
import json

import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product
from app.services import products
from app.services.products import ProductSourceError
from tests.conftest import FakeWeb

API = "/api/v1/products"
SHEET_URL = "https://docs.google.com/spreadsheets/d/abc123/edit#gid=42"
SHEET_CSV = "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=42"

# Deliberately "messy" like a real shop's sheet: a title row, Persian digits, words for stock.
CSV = """لیست محصولات مزون,,,,,
نام کالا,رنگ,سایز,قیمت (تومان),موجودی,جنس
مانتو کتان,مشکی,44,"۱,۲۵۰,۰۰۰",۳,کتان ترک
مانتو کتان,مشکی,46,"1,250,000",ناموجود,کتان ترک
مانتو کتان,سرمه‌ای,44,1250000,موجود,کتان ترک
شومیز حریر,سفید,آزاد,890000,2,
,,,,,
"""


def _serve_sheet(fake_web: FakeWeb, body: str = CSV) -> None:
    fake_web.files[SHEET_CSV] = (200, body.encode(), "text/csv")


def test_download_url_conversion() -> None:
    assert products.download_url(SHEET_URL) == SHEET_CSV
    assert products.download_url(
        "https://docs.google.com/spreadsheets/d/abc123/edit?usp=sharing"
    ).endswith("/abc123/export?format=csv&gid=0")
    assert (
        products.download_url("https://drive.google.com/file/d/XYZ/view?usp=sharing")
        == "https://drive.google.com/uc?export=download&id=XYZ"
    )
    for bad in ("https://evil.example.com/sheet", "file:///etc/passwd", "http://169.254.169.254/"):
        with pytest.raises(ProductSourceError):
            products.download_url(bad)


def test_parse_and_map_messy_sheet() -> None:
    table = products.parse_table(CSV.encode(), "csv")
    assert table.headers == ["نام کالا", "رنگ", "سایز", "قیمت (تومان)", "موجودی", "جنس"]
    assert len(table.rows) == 4  # title row and blank row skipped

    mapping = products.suggest_mapping(table.headers)
    assert mapping == {
        "name": "نام کالا",
        "color": "رنگ",
        "size": "سایز",
        "price": "قیمت (تومان)",
        "stock": "موجودی",
        "description": "جنس",
    }
    items = products.rows_to_products(table, mapping)
    assert items[0]["price"] == 1250000
    assert [i["stock"] for i in items] == [3, 0, 1, 2]


def test_parse_xlsx() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Name", "Price", "Qty", "Supplier"])
    sheet.append(["Scarf", 350000.0, 5, "Tabriz"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    table = products.parse_table(buffer.getvalue(), "xlsx")
    mapping = products.suggest_mapping(table.headers)
    assert mapping == {"name": "Name", "price": "Price", "stock": "Qty"}
    [item] = products.rows_to_products(table, mapping)
    assert item["price"] == 350000
    assert item["extra"] == {"Supplier": "Tabriz"}  # unmapped columns are kept for the bot


def test_parse_stock_words() -> None:
    assert products.parse_stock("ناموجود") == 0
    assert products.parse_stock("تمام شد") == 0
    assert products.parse_stock("موجود") == 1
    assert products.parse_stock("۱۲ عدد") == 12
    assert products.parse_stock("") is None


async def test_sheet_preview_and_connect(
    client: AsyncClient, auth_headers: dict, fake_web: FakeWeb
) -> None:
    _serve_sheet(fake_web)
    preview = await client.post(
        f"{API}/sheet/preview", headers=auth_headers, json={"url": SHEET_URL}
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["row_count"] == 4
    assert body["suggested_mapping"]["name"] == "نام کالا"
    assert body["sample_rows"][0]["رنگ"] == "مشکی"

    connected = await client.put(
        f"{API}/sheet",
        headers=auth_headers,
        json={"url": SHEET_URL, "column_mapping": body["suggested_mapping"]},
    )
    assert connected.status_code == 200
    source = connected.json()
    assert source["connected"] and source["kind"] == "google_sheet"
    assert source["product_count"] == 4
    assert source["last_error"] is None

    listing = (await client.get(API, headers=auth_headers)).json()
    assert listing["total"] == 4
    found = (await client.get(API, headers=auth_headers, params={"q": "شومیز"})).json()
    assert [p["name"] for p in found["items"]] == ["شومیز حریر"]


async def test_private_sheet_gives_sharing_instructions(
    client: AsyncClient, auth_headers: dict, fake_web: FakeWeb
) -> None:
    fake_web.files[SHEET_CSV] = (200, b"<html>Sign in</html>", "text/html; charset=utf-8")
    resp = await client.post(f"{API}/sheet/preview", headers=auth_headers, json={"url": SHEET_URL})
    assert resp.status_code == 422
    assert "Anyone with the link" in resp.json()["detail"]


async def test_connect_rejects_bad_mapping(
    client: AsyncClient, auth_headers: dict, fake_web: FakeWeb
) -> None:
    _serve_sheet(fake_web)
    no_name = await client.put(
        f"{API}/sheet", headers=auth_headers, json={"url": SHEET_URL, "column_mapping": {}}
    )
    assert no_name.status_code == 422
    wrong_header = await client.put(
        f"{API}/sheet",
        headers=auth_headers,
        json={"url": SHEET_URL, "column_mapping": {"name": "وجود ندارد"}},
    )
    assert wrong_header.status_code == 422


async def test_failed_resync_keeps_old_products(
    client: AsyncClient, auth_headers: dict, fake_web: FakeWeb
) -> None:
    _serve_sheet(fake_web)
    mapping = products.suggest_mapping(products.parse_table(CSV.encode(), "csv").headers)
    await client.put(
        f"{API}/sheet", headers=auth_headers, json={"url": SHEET_URL, "column_mapping": mapping}
    )
    # The owner un-shares the sheet.
    fake_web.files[SHEET_CSV] = (403, b"", "text/plain")
    resp = await client.post(f"{API}/sync", headers=auth_headers)
    assert resp.status_code == 422

    source = (await client.get(f"{API}/source", headers=auth_headers)).json()
    assert source["last_error"] is not None
    assert source["product_count"] == 4  # the bot keeps using the last good copy

    dashboard = (await client.get("/api/v1/dashboard", headers=auth_headers)).json()
    assert dashboard["setup"]["product_error"] == source["last_error"]


async def test_file_import(client: AsyncClient, auth_headers: dict) -> None:
    files = {"file": ("stock.csv", CSV.encode(), "text/csv")}
    preview = await client.post(f"{API}/file/preview", headers=auth_headers, files=files)
    assert preview.status_code == 200
    mapping = preview.json()["suggested_mapping"]

    imported = await client.post(
        f"{API}/file",
        headers=auth_headers,
        files=files,
        data={"column_mapping": json.dumps(mapping, ensure_ascii=False)},
    )
    assert imported.status_code == 200
    assert imported.json()["kind"] == "upload"
    assert imported.json()["product_count"] == 4

    # Only Google Sheets can be re-synced.
    assert (await client.post(f"{API}/sync", headers=auth_headers)).status_code == 400

    bad = await client.post(
        f"{API}/file/preview",
        headers=auth_headers,
        files={"file": ("stock.pdf", b"x", "application/pdf")},
    )
    assert bad.status_code == 422


async def test_remove_source(client: AsyncClient, auth_headers: dict) -> None:
    files = {"file": ("stock.csv", CSV.encode(), "text/csv")}
    await client.post(
        f"{API}/file",
        headers=auth_headers,
        files=files,
        data={"column_mapping": json.dumps({"name": "نام کالا"}, ensure_ascii=False)},
    )
    assert (await client.delete(f"{API}/source", headers=auth_headers)).status_code == 204
    assert (await client.get(f"{API}/source", headers=auth_headers)).json()["connected"] is False
    assert (await client.get(API, headers=auth_headers)).json()["total"] == 0


async def test_template_and_fields(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get(f"{API}/template.csv", headers=auth_headers)
    assert resp.content.startswith(b"\xef\xbb\xbf")
    headers = products.parse_table(resp.content, "csv").headers
    # Our own template must map perfectly onto our fields.
    assert set(products.suggest_mapping(headers)) == set(products.FIELDS)

    fields = (await client.get(f"{API}/fields", headers=auth_headers)).json()
    assert [f["key"] for f in fields if f["required"]] == ["name"]


async def test_search_normalizes_persian(db: AsyncSession) -> None:
    import uuid

    shop_id = uuid.uuid4()
    db.add_all(
        [
            Product(shop_id=shop_id, name="مانتو كتان", color="مشکی", size="44", extra={}),
            Product(shop_id=shop_id, name="مانتو کتان", color="سفید", size="46", extra={}),
            Product(shop_id=shop_id, name="شال نخی", color="مشکی", extra={}),
        ]
    )
    await db.flush()
    # Arabic kaf in the stored name, Persian digits in the query: still a match.
    found = await products.search_products(db, shop_id, "مانتو کتان", size="۴۴")
    assert [(p.color, p.size) for p in found] == [("مشکی", "44")]
    assert await products.search_products(db, shop_id, "مانتو", color="قرمز") == []
    assert len(await products.search_products(db, shop_id, "مشکی")) == 0  # colour isn't a name


def test_catalogue_overview_cheapest_first_and_stock() -> None:
    import uuid

    shop_id = uuid.uuid4()
    items = [
        Product(
            shop_id=shop_id,
            name="مانتو کتان",
            category="مانتو",
            color="مشکی",
            size="44",
            price=1250000,
            stock=3,
            extra={},
        ),
        Product(
            shop_id=shop_id,
            name="مانتو کتان",
            category="مانتو",
            color="سرمه‌ای",
            size="44",
            price=1250000,
            stock=0,
            extra={},
        ),
        Product(
            shop_id=shop_id,
            name="شومیز حریر",
            color="سفید",
            size="آزاد",
            price=890000,
            stock=7,
            extra={},
        ),
        Product(shop_id=shop_id, name="شال", price=300000, stock=0, extra={}),
    ]
    lines = products.catalogue_overview(items).splitlines()
    assert lines == [
        "- شال; 300,000 toman; out of stock",
        "- شومیز حریر; 890,000 toman; colours in stock: سفید; sizes in stock: آزاد",
        "- مانتو کتان (مانتو); 1,250,000 toman; colours in stock: مشکی; sizes in stock: 44",
    ]
    capped = products.catalogue_overview(items, max_lines=1).splitlines()
    assert capped[-1] == "- ...and 2 more products (use search_products)"
