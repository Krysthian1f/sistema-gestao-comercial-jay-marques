from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index

from app.extensions import db


class User(db.Model):
    """Mantida apenas para preservar a tabela ``users`` já existente.

    O sistema não usa mais autenticação: esta tabela não é consultada para
    liberar acesso e nenhum registro dela é alterado pela aplicação.
    """

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


class Customer(db.Model):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_active_name", "is_active", "name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False)
    normalized_phone = db.Column(db.String(15), nullable=False, unique=True)
    email = db.Column(db.String(254), nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sales = db.relationship("Sale", back_populates="customer", lazy="select")


class Sale(db.Model):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_sale_total_nonnegative"),
        db.CheckConstraint(
            "payment_method IN ('dinheiro', 'pix', 'cartao_credito', 'cartao_debito', 'transferencia')",
            name="ck_sale_payment_method",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    idempotency_key = db.Column(db.String(36), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True)
    customer_name = db.Column(db.String(120), nullable=False, default="Consumidor não identificado")
    payment_method = db.Column(db.String(20), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    customer = db.relationship("Customer", back_populates="sales")
    items = db.relationship("SaleItem", back_populates="sale", lazy="select", cascade="all, delete-orphan", order_by="SaleItem.id")


class SaleItem(db.Model):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_sale_item_price_nonnegative"),
        CheckConstraint("unit_cost >= 0", name="ck_sale_item_cost_nonnegative"),
        CheckConstraint("subtotal >= 0", name="ck_sale_item_subtotal_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_code = db.Column(db.String(20), nullable=False)
    product_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    stock_movement_id = db.Column(db.Integer, db.ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=False, unique=True)
    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product", lazy="joined")
    stock_movement = db.relationship("StockMovement", lazy="joined")


class FinancialEntry(db.Model):
    __tablename__ = "financial_entries"
    __table_args__ = (
        db.CheckConstraint("kind IN ('receita', 'despesa')", name="ck_financial_entry_kind"),
        CheckConstraint("amount >= 0", name="ck_financial_entry_amount_nonnegative"),
        Index("ix_financial_entries_kind_occurred", "kind", "occurred_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(240), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True, unique=True)
    idempotency_key = db.Column(db.String(36), nullable=True, unique=True)
    sale = db.relationship("Sale", backref=db.backref("financial_entry", uselist=False))
