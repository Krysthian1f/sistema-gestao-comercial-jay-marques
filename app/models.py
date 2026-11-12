from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index
from flask_login import UserMixin

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("failed_login_attempts >= 0", name="ck_user_failed_login_nonnegative"),)

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("cost_price >= 0", name="ck_product_cost_nonnegative"),
        CheckConstraint("selling_price >= 0", name="ck_product_price_nonnegative"),
        CheckConstraint("stock_quantity >= 0", name="ck_product_stock_nonnegative"),
        CheckConstraint("minimum_stock >= 0", name="ck_product_minimum_nonnegative"),
        Index("ix_products_active_name", "is_active", "name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    cost_price = db.Column(db.Numeric(12, 2), nullable=False)
    selling_price = db.Column(db.Numeric(12, 2), nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    minimum_stock = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    movements = db.relationship("StockMovement", back_populates="product", lazy="select", order_by="StockMovement.created_at.desc()")

    @staticmethod
    def next_code() -> str:
        last_id = db.session.query(db.func.max(Product.id)).scalar() or 0
        return f"JM-{last_id + 1:06d}"


class StockMovement(db.Model):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_movement_quantity_positive"),
        db.CheckConstraint("movement_type IN ('entrada', 'saida')", name="ck_movement_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    movement_type = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(240), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    product = db.relationship("Product", back_populates="movements")
