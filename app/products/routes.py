from decimal import Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Product, StockMovement
from app.products import products


def _integer(value: str, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Informe um valor inteiro válido para {label}.") from None
    if parsed < 0:
        raise ValueError(f"{label.capitalize()} não pode ser negativo.")
    return parsed


def _money(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value.strip().replace(",", "."))
    except (AttributeError, InvalidOperation):
        raise ValueError(f"Informe um valor válido para {label}.") from None
    if not parsed.is_finite() or parsed < 0 or parsed.as_tuple().exponent < -2:
        raise ValueError(f"{label.capitalize()} deve ser positivo ou zero, com até duas casas decimais.")
    return parsed


def _product_form_data(form, *, creating=False):
    name = form.get("name", "").strip()
    category = form.get("category", "").strip()
    if not name or len(name) > 120:
        raise ValueError("Informe um nome de produto com até 120 caracteres.")
    if not category or len(category) > 80:
        raise ValueError("Informe uma categoria com até 80 caracteres.")
    description = form.get("description", "").strip()
    if len(description) > 5000:
        raise ValueError("A descrição deve ter no máximo 5.000 caracteres.")
    data = {
        "name": name,
        "category": category,
        "description": description,
        "cost_price": _money(form.get("cost_price", ""), "preço de custo"),
        "selling_price": _money(form.get("selling_price", ""), "preço de venda"),
        "minimum_stock": _integer(form.get("minimum_stock", ""), "estoque mínimo"),
    }
    if creating:
        data["stock_quantity"] = _integer(form.get("stock_quantity", "0"), "quantidade em estoque")
    return data


def _active_product(product_id):
    return db.get_or_404(Product, product_id, description="Produto não encontrado.")


@products.get("/")
def index():
    query = request.args.get("q", "").strip()
    low_stock = request.args.get("baixo_estoque") == "1"
    statement = db.select(Product).where(Product.is_active.is_(True))
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(Product.name.ilike(pattern), Product.code.ilike(pattern), Product.category.ilike(pattern)))
    if low_stock:
        statement = statement.where(Product.stock_quantity <= Product.minimum_stock)
    items = db.session.scalars(statement.order_by(Product.name)).all()
    low_stock_count = db.session.scalar(
        db.select(db.func.count()).select_from(Product).where(
            Product.is_active.is_(True), Product.stock_quantity <= Product.minimum_stock
        )
    )
    return render_template("products/index.html", products=items, query=query, low_stock=low_stock, low_stock_count=low_stock_count)


@products.route("/novo", methods=["GET", "POST"])
def create():
    values = request.form if request.method == "POST" else {}
    if request.method == "POST":
        try:
            data = _product_form_data(request.form, creating=True)
            product = Product(code=Product.next_code(), **data)
            db.session.add(product)
            db.session.flush()
            if product.stock_quantity:
                db.session.add(StockMovement(product=product, movement_type="entrada", quantity=product.stock_quantity, reason="Saldo inicial do cadastro"))
            db.session.commit()
            flash("Produto cadastrado com sucesso.", "success")
            return redirect(url_for("products.detail", product_id=product.id))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Não foi possível gerar um código exclusivo. Tente novamente.", "danger")
    return render_template("products/form.html", product=None, values=values, title="Cadastrar produto")


@products.get("/<int:product_id>")
def detail(product_id):
    product = _active_product(product_id)
    return render_template("products/detail.html", product=product)


@products.route("/<int:product_id>/editar", methods=["GET", "POST"])
def edit(product_id):
    product = _active_product(product_id)
    values = request.form if request.method == "POST" else {}
    if request.method == "POST":
        try:
            for field, value in _product_form_data(request.form).items():
                setattr(product, field, value)
            db.session.commit()
            flash("Produto atualizado com sucesso.", "success")
            return redirect(url_for("products.detail", product_id=product.id))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
            product = _active_product(product_id)
    return render_template("products/form.html", product=product, values=values, title="Editar produto")


@products.route("/<int:product_id>/excluir", methods=["GET", "POST"])
def deactivate(product_id):
    product = _active_product(product_id)
    if request.method == "POST":
        product.is_active = False
        db.session.commit()
        flash("Produto removido do catálogo. O histórico de estoque foi preservado.", "success")
        return redirect(url_for("products.index"))
    return render_template("products/confirm_delete.html", product=product)
