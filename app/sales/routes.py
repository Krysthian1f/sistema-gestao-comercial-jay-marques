from datetime import datetime, timezone
from decimal import Decimal
import uuid

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError

from app.extensions import db
from app.models import Customer, FinancialEntry, Product, Sale, SaleItem, StockMovement
from app.sales import sales


PAYMENT_METHODS = {
    "dinheiro": "Dinheiro",
    "pix": "Pix",
    "cartao_credito": "Cartão de crédito",
    "cartao_debito": "Cartão de débito",
    "transferencia": "Transferência",
}


def _sale_items_from_form(form):
    submitted = []
    for key, value in form.items():
        if not key.startswith("quantity_"):
            continue
        try:
            product_id = int(key.removeprefix("quantity_"))
            quantity = int(value or "0")
        except ValueError:
            raise ValueError("Confira as quantidades informadas nos produtos.") from None
        if quantity < 0:
            raise ValueError("A quantidade vendida não pode ser negativa.")
        if quantity:
            submitted.append((product_id, quantity))
    if not submitted:
        raise ValueError("Informe a quantidade de pelo menos um produto.")
    if len({product_id for product_id, _ in submitted}) != len(submitted):
        raise ValueError("O mesmo produto foi informado mais de uma vez.")
    return submitted


@sales.get("/")
def index():
    records = db.session.scalars(db.select(Sale).order_by(Sale.created_at.desc(), Sale.id.desc()).limit(100)).all()
    return render_template("sales/index.html", sales=records)


@sales.route("/nova", methods=["GET", "POST"])
def create():
    active_products = db.session.scalars(
        db.select(Product).where(Product.is_active.is_(True), Product.stock_quantity > 0).order_by(Product.name)
    ).all()
    active_customers = db.session.scalars(
        db.select(Customer).where(Customer.is_active.is_(True)).order_by(Customer.name)
    ).all()
    idempotency_key = str(uuid.uuid4())

    if request.method == "POST":
        try:
            idempotency_key = str(uuid.UUID(request.form.get("idempotency_key", "")))
            prior_sale = db.session.scalar(db.select(Sale).where(Sale.idempotency_key == idempotency_key))
            if prior_sale:
                flash("Esta venda já havia sido registrada.", "info")
                return redirect(url_for("sales.detail", sale_id=prior_sale.id))

            payment_method = request.form.get("payment_method", "")
            if payment_method not in PAYMENT_METHODS:
                raise ValueError("Selecione uma forma de pagamento válida.")
            requested_items = _sale_items_from_form(request.form)
            customer_id_value = request.form.get("customer_id", "").strip()
            customer = None
            if customer_id_value:
                try:
                    customer_id = int(customer_id_value)
                except ValueError:
                    raise ValueError("Selecione um cliente válido.") from None
                customer = db.session.scalar(
                    db.select(Customer).where(Customer.id == customer_id, Customer.is_active.is_(True))
                )
                if customer is None:
                    raise ValueError("O cliente selecionado não está disponível.")

            products = {}
            for product_id, quantity in requested_items:
                product = db.session.scalar(
                    db.select(Product).where(Product.id == product_id, Product.is_active.is_(True)).with_for_update()
                )
                if product is None:
                    raise ValueError("Um dos produtos selecionados não está disponível.")
                if quantity > product.stock_quantity:
                    raise ValueError(f"Estoque insuficiente para {product.name}.")
                products[product_id] = (product, quantity)

            code = f"JM-V-{uuid.uuid4().hex[:8].upper()}"
            sale = Sale(
                code=code,
                idempotency_key=idempotency_key,
                customer=customer,
                customer_name=customer.name if customer else "Consumidor não identificado",
                payment_method=payment_method,
                total_amount=Decimal("0.00"),
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(sale)
            db.session.flush()

            total = Decimal("0.00")
            for product, quantity in products.values():
                changed = db.session.execute(
                    update(Product)
                    .where(
                        Product.id == product.id,
                        Product.is_active.is_(True),
                        Product.stock_quantity >= quantity,
                    )
                    .values(stock_quantity=Product.stock_quantity - quantity)
                    .execution_options(synchronize_session=False)
                )
                if changed.rowcount != 1:
                    raise ValueError(f"Estoque insuficiente para {product.name}.")

                subtotal = (Decimal(product.selling_price) * quantity).quantize(Decimal("0.01"))
                item = SaleItem(
                    sale=sale,
                    product=product,
                    product_code=product.code,
                    product_name=product.name,
                    quantity=quantity,
                    unit_price=product.selling_price,
                    unit_cost=product.cost_price,
                    subtotal=subtotal,
                )
                movement = StockMovement(
                    product=product,
                    movement_type="saida",
                    quantity=quantity,
                    reason=f"Venda {code}",
                )
                item.stock_movement = movement
                db.session.add(item)
                total += subtotal

            sale.total_amount = total
            db.session.add(
                FinancialEntry(
                    kind="receita",
                    category="Venda",
                    description=f"Recebimento da venda {code}",
                    amount=total,
                    occurred_at=sale.created_at,
                    sale=sale,
                )
            )
            db.session.commit()
            flash("Venda registrada e estoque atualizado.", "success")
            return redirect(url_for("sales.detail", sale_id=sale.id))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            prior_sale = db.session.scalar(db.select(Sale).where(Sale.idempotency_key == idempotency_key))
            if prior_sale:
                flash("Esta venda já havia sido registrada.", "info")
                return redirect(url_for("sales.detail", sale_id=prior_sale.id))
            flash("Não foi possível salvar a venda. Atualize a página e tente novamente.", "danger")
        except OperationalError:
            db.session.rollback()
            flash("O banco está ocupado. Nenhuma venda foi registrada; tente novamente.", "danger")

    return render_template(
        "sales/form.html",
        products=active_products,
        customers=active_customers,
        payment_methods=PAYMENT_METHODS,
        idempotency_key=idempotency_key,
    )


@sales.get("/<int:sale_id>")
def detail(sale_id):
    sale = db.get_or_404(Sale, sale_id, description="Venda não encontrada.")
    return render_template("sales/detail.html", sale=sale, payment_label=PAYMENT_METHODS.get(sale.payment_method, sale.payment_method))
