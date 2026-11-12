from datetime import datetime, timedelta, timezone

from flask import render_template

from app.dashboard import dashboard
from app.extensions import db
from app.models import Product


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
    return render_template("dashboard/index.html", today=today, product_count=product_count, low_stock_count=low_stock_count)
