from flask import flash, redirect, request, url_for
from sqlalchemy import select

from app.extensions import db
from app.models import Product, StockMovement
from app.inventory import inventory


@inventory.post("/produtos/<int:product_id>/movimentacoes")
def move_stock(product_id):
    product = db.get_or_404(Product, product_id, description="Produto não encontrado.")
    if not product.is_active:
        flash("Não é possível movimentar um produto removido do catálogo.", "danger")
        return redirect(url_for("products.index"))

    movement_type = request.form.get("movement_type", "")
    reason = request.form.get("reason", "").strip()
    try:
        quantity = int(request.form.get("quantity", ""))
        if movement_type not in {"entrada", "saida"}:
            raise ValueError("Selecione entrada ou saída de estoque.")
        if quantity <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")
        if not reason or len(reason) > 240:
            raise ValueError("Informe o motivo da movimentação (até 240 caracteres).")
        if movement_type == "saida" and quantity > product.stock_quantity:
            raise ValueError("A saída é maior que o estoque disponível.")
        product.stock_quantity += quantity if movement_type == "entrada" else -quantity
        db.session.add(StockMovement(product=product, movement_type=movement_type, quantity=quantity, reason=reason))
        db.session.commit()
        flash("Movimentação registrada com sucesso.", "success")
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "danger")
    return redirect(url_for("products.detail", product_id=product.id))
