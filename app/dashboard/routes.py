from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import render_template

from app.dashboard import dashboard
from app.extensions import db
from app.models import Customer, FinancialEntry, Product, Sale, StockMovement


@dashboard.get("/")
def index():
    brasilia = timezone(timedelta(hours=-3))
    today = datetime.now(brasilia).strftime("%d/%m/%Y")
    product_count = db.session.scalar(
        db.select(db.func.count()).select_from(Product).where(Product.is_active.is_(True))
    )
    low_stock_count = db.session.scalar(
        db.select(db.func.count()).select_from(Product).where(
            Product.is_active.is_(True), Product.stock_quantity <= Product.minimum_stock
        )
    )
    customer_count = db.session.scalar(
        db.select(db.func.count()).select_from(Customer).where(Customer.is_active.is_(True))
    )
    sales_count = db.session.scalar(db.select(db.func.count()).select_from(Sale))
    revenue = db.session.scalar(db.select(db.func.coalesce(db.func.sum(Sale.total_amount), 0))) or Decimal("0.00")
    finance_entries = db.session.scalars(db.select(FinancialEntry)).all()
    balance = sum(
        (entry.amount if entry.kind == "receita" else -entry.amount for entry in finance_entries),
        Decimal("0.00"),
    )

    events = []
    for movement in db.session.scalars(
        db.select(StockMovement).order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(10)
    ):
        events.append({
            "created_at": movement.created_at,
            "title": "Entrada de estoque" if movement.movement_type == "entrada" else "Saída de estoque",
            "description": f"{movement.product.name} · {movement.quantity} unidade(s) · {movement.reason}",
        })
    for sale in db.session.scalars(db.select(Sale).order_by(Sale.created_at.desc(), Sale.id.desc()).limit(10)):
        events.append({
            "created_at": sale.created_at,
            "title": "Venda registrada",
            "description": f"{sale.code} · {sale.customer_name} · R$ {sale.total_amount:.2f}".replace(".", ","),
        })
    events.sort(key=lambda event: event["created_at"], reverse=True)

    return render_template(
        "dashboard/index.html",
        today=today,
        product_count=product_count,
        low_stock_count=low_stock_count,
        customer_count=customer_count,
        sales_count=sales_count,
        revenue=revenue,
        financial_balance=balance,
        recent_events=events[:8],
    )
