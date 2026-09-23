import codecs
import csv
import io
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select

from app.api.deps import CurrentShop, DbSession, HttpClient
from app.api.uploads import read_upload
from app.core.timeutil import utcnow
from app.models import Product, ProductSource, ProductSourceKind, Shop
from app.services import products
from app.services.products import ProductSourceError

router = APIRouter(prefix="/products", tags=["products"])


class FieldOut(BaseModel):
    key: str
    label: str
    required: bool


class PreviewOut(BaseModel):
    headers: list[str]
    sample_rows: list[dict[str, str]]
    row_count: int
    # {our_field: sheet_header}; the panel lets the owner correct it before saving.
    suggested_mapping: dict[str, str]


class SheetPreviewIn(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


class SheetConnectIn(BaseModel):
    url: str = Field(min_length=10, max_length=2000)
    column_mapping: dict[str, str]


class SourceOut(BaseModel):
    connected: bool
    kind: Literal["google_sheet", "upload"] | None = None
    url: str | None = None
    column_mapping: dict[str, str] = {}
    product_count: int = 0
    last_synced_at: datetime | None = None
    # Persian message when the last sync failed (e.g. sheet no longer shared). The previous
    # product data stays in use until a sync succeeds.
    last_error: str | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str | None
    name: str
    category: str | None
    color: str | None
    size: str | None
    price: Decimal | None
    stock: int | None
    description: str | None
    extra: dict[str, Any]


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int


@router.get("/fields", response_model=list[FieldOut])
async def fields() -> list[FieldOut]:
    """Our product fields, for the column-mapping step."""
    return [
        FieldOut(key=f, label=products.FIELD_LABELS[f], required=f == "name")
        for f in products.FIELDS
    ]


@router.get("/template.csv", response_class=Response)
async def template() -> Response:
    """A ready-made product table; opens correctly in Excel and imports into Google Sheets."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(products.TEMPLATE_HEADERS)
    writer.writerow(products.TEMPLATE_EXAMPLE)
    return Response(
        content=codecs.BOM_UTF8 + buffer.getvalue().encode(),  # BOM so Excel detects UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="products-template.csv"'},
    )


@router.post("/sheet/preview", response_model=PreviewOut)
async def preview_sheet(body: SheetPreviewIn, shop: CurrentShop, http: HttpClient) -> PreviewOut:
    try:
        table = await products.fetch_table(http, body.url)
    except ProductSourceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return _preview(table)


@router.put("/sheet", response_model=SourceOut)
async def connect_sheet(
    body: SheetConnectIn, shop: CurrentShop, db: DbSession, http: HttpClient
) -> SourceOut:
    """Save the Google Sheet link + mapping and import it now. Re-synced every few minutes."""
    try:
        table = await products.fetch_table(http, body.url)
        products.validate_mapping(body.column_mapping, table.headers)
    except ProductSourceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    source = await _upsert_source(
        db, shop, ProductSourceKind.GOOGLE_SHEET, body.url.strip(), body.column_mapping
    )
    try:
        await products.sync_source(db, source, http, table=table)
    except ProductSourceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return await _source_out(db, shop)


@router.post("/file/preview", response_model=PreviewOut)
async def preview_file(file: UploadFile, shop: CurrentShop) -> PreviewOut:
    return _preview(await _parse_upload(file))


@router.post("/file", response_model=SourceOut)
async def import_file(
    file: UploadFile,
    shop: CurrentShop,
    db: DbSession,
    column_mapping: str = Form(description='JSON object, e.g. {"name": "نام محصول"}'),
) -> SourceOut:
    """One-off import of an Excel/CSV file (not re-synced; upload again to update)."""
    try:
        mapping = json.loads(column_mapping)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "column_mapping باید JSON باشد"
        ) from None
    if not isinstance(mapping, dict) or not all(isinstance(v, str) for v in mapping.values()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "column_mapping نامعتبر است")
    table = await _parse_upload(file)
    try:
        products.validate_mapping(mapping, table.headers)
    except ProductSourceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    source = await _upsert_source(db, shop, ProductSourceKind.UPLOAD, None, mapping)
    await products.replace_products(db, shop.id, products.rows_to_products(table, mapping))
    source.last_synced_at = utcnow()
    source.last_error = None
    await db.commit()
    return await _source_out(db, shop)


@router.post("/sync", response_model=SourceOut)
async def sync_now(shop: CurrentShop, db: DbSession, http: HttpClient) -> SourceOut:
    source = await _get_source(db, shop)
    if source is None or source.kind != ProductSourceKind.GOOGLE_SHEET:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "گوگل شیتی متصل نیست.")
    try:
        await products.sync_source(db, source, http)
    except ProductSourceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return await _source_out(db, shop)


@router.get("/source", response_model=SourceOut)
async def get_source(shop: CurrentShop, db: DbSession) -> SourceOut:
    return await _source_out(db, shop)


@router.delete("/source", status_code=status.HTTP_204_NO_CONTENT)
async def remove_source(shop: CurrentShop, db: DbSession) -> None:
    """Disconnect the product table and delete the imported products."""
    await db.execute(delete(Product).where(Product.shop_id == shop.id))
    await db.execute(delete(ProductSource).where(ProductSource.shop_id == shop.id))
    await db.commit()


@router.get("", response_model=ProductPage)
async def list_products(
    shop: CurrentShop,
    db: DbSession,
    q: str | None = Query(default=None, max_length=100, description="search name/code"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ProductPage:
    if q:
        found = await products.search_products(db, shop.id, q, limit=limit)
        return ProductPage(items=[ProductOut.model_validate(p) for p in found], total=len(found))
    total = await db.scalar(
        select(func.count()).select_from(Product).where(Product.shop_id == shop.id)
    )
    rows = await db.scalars(
        select(Product)
        .where(Product.shop_id == shop.id)
        .order_by(Product.name, Product.color, Product.size)
        .offset(offset)
        .limit(limit)
    )
    return ProductPage(items=[ProductOut.model_validate(p) for p in rows], total=total or 0)


def _preview(table: products.Table) -> PreviewOut:
    return PreviewOut(
        headers=table.headers,
        sample_rows=table.rows[:5],
        row_count=len(table.rows),
        suggested_mapping=products.suggest_mapping(table.headers),
    )


async def _parse_upload(file: UploadFile) -> products.Table:
    data = await read_upload(file)
    name = (file.filename or "").lower()
    if name.endswith(".xlsx"):
        kind = "xlsx"
    elif name.endswith(".csv"):
        kind = "csv"
    else:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "فقط فایل‌های xlsx و csv پشتیبانی می‌شوند."
        )
    try:
        return products.parse_table(data, kind)
    except ProductSourceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


async def _get_source(db: DbSession, shop: Shop) -> ProductSource | None:
    return await db.scalar(select(ProductSource).where(ProductSource.shop_id == shop.id))


async def _upsert_source(
    db: DbSession, shop: Shop, kind: ProductSourceKind, url: str | None, mapping: dict[str, str]
) -> ProductSource:
    source = await _get_source(db, shop)
    if source is None:
        source = ProductSource(shop_id=shop.id, kind=kind)
        db.add(source)
    source.kind = kind
    source.url = url
    source.column_mapping = mapping
    await db.commit()
    return source


async def _source_out(db: DbSession, shop: Shop) -> SourceOut:
    source = await _get_source(db, shop)
    if source is None:
        return SourceOut(connected=False)
    await db.refresh(source)
    count = await db.scalar(
        select(func.count()).select_from(Product).where(Product.shop_id == shop.id)
    )
    return SourceOut(
        connected=True,
        kind=source.kind.value,
        url=source.url,
        column_mapping=source.column_mapping,
        product_count=count or 0,
        last_synced_at=source.last_synced_at,
        last_error=source.last_error,
    )
