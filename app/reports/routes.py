import csv
from datetime import date, timedelta
from io import StringIO

from flask import Response, flash, render_template, request, url_for

from app.extensions import db
from app.models import FinancialEntry, Product, Sale, StockMovement
from app.finance.routes import _parse_filter_date, _utc_boundary
from app.reports import reports
from app.timeutils import format_brasilia_date, format_brasilia_datetime


REPORTS = {
    "vendas": "Vendas",
    "produtos": "Produtos",
    "estoque": "Movimentações de estoque",
    "financeiro": "Financeiro",
}


def _date_filters(start: date | None, end: date | None, field):
    conditions = []
    if start:
        conditions.append(field >= _utc_boundary(start))
    if end:
        conditions.append(field < _utc_boundary(end + timedelta(days=1)))
    return conditions


def _report_data(report_type, start_date=None, end_date=None):
    if report_type == "vendas":
        rows = db.session.execute(
            db.select(Sale).where(*_date_filters(start_date, end_date, Sale.created_at)).order_by(Sale.created_at.desc())
        ).scalars().all()
        headers = ["Código", "Data", "Cliente", "Forma de pagamento", "Total"]
        values = [[sale.code, format_brasilia_datetime(sale.created_at), sale.customer_name, sale.payment_method, sale.total_amount] for sale in rows]
    elif report_type == "produtos":
        rows = db.session.scalars(
            db.select(Product).where(Product.is_active.is_(True), *_date_filters(start_date, end_date, Product.created_at)).order_by(Product.name)
        ).all()
        headers = ["Código", "Produto", "Categoria", "Preço de custo", "Preço de venda", "Estoque", "Estoque mínimo"]
        values = [[item.code, item.name, item.category, item.cost_price, item.selling_price, item.stock_quantity, item.minimum_stock] for item in rows]
    elif report_type == "estoque":
        rows = db.session.execute(
            db.select(StockMovement, Product).join(Product).where(
                *_date_filters(start_date, end_date, StockMovement.created_at)
            ).order_by(StockMovement.created_at.desc())
        ).all()
        headers = ["Data", "Código do produto", "Produto", "Tipo", "Quantidade", "Motivo"]
        values = [[format_brasilia_datetime(movement.created_at), product.code, product.name, movement.movement_type, movement.quantity, movement.reason] for movement, product in rows]
    else:
        rows = db.session.scalars(
            db.select(FinancialEntry).where(
                *_date_filters(start_date, end_date, FinancialEntry.occurred_at)
            ).order_by(FinancialEntry.occurred_at.desc())
        ).all()
        headers = ["Data", "Tipo", "Categoria", "Descrição", "Origem", "Valor"]
        values = [[format_brasilia_date(entry.occurred_at), entry.kind, entry.category, entry.description, "Venda" if entry.sale_id else "Manual", entry.amount] for entry in rows]
    return headers, values


def _summary(report_type, rows):
    if report_type == "vendas":
        return [f"Faturamento no período: R$ {sum((row.total_amount for row in rows), start=0):.2f}".replace(".", ",")]
    if report_type == "produtos":
        unit_count = sum(product.stock_quantity for product in rows)
        stock_cost = sum((product.cost_price * product.stock_quantity for product in rows), start=0)
        return [f"Produtos ativos: {len(rows)}", f"Unidades em estoque: {unit_count}", f"Valor de custo em estoque: R$ {stock_cost:.2f}".replace(".", ",")]
    if report_type == "estoque":
        incoming = sum(movement.quantity for movement, _product in rows if movement.movement_type == "entrada")
        outgoing = sum(movement.quantity for movement, _product in rows if movement.movement_type == "saida")
        return [f"Entradas: {incoming} unidade(s)", f"Saídas: {outgoing} unidade(s)"]
    revenue = sum((entry.amount for entry in rows if entry.kind == "receita"), start=0)
    expenses = sum((entry.amount for entry in rows if entry.kind == "despesa"), start=0)
    return [
        f"Receitas: R$ {revenue:.2f}".replace(".", ","),
        f"Despesas: R$ {expenses:.2f}".replace(".", ","),
        f"Saldo: R$ {revenue - expenses:.2f}".replace(".", ","),
    ]


def _filter_values():
    start_date = _parse_filter_date(request.args.get("inicio", ""), "data inicial")
    end_date = _parse_filter_date(request.args.get("fim", ""), "data final")
    if start_date and end_date and start_date > end_date:
        raise ValueError("A data inicial deve ser anterior ou igual à data final.")
    return start_date, end_date


@reports.get("/")
def index():
    report_type = request.args.get("tipo", "vendas")
    if report_type not in REPORTS:
        report_type = "vendas"
        flash("Tipo de relatório inválido. Exibindo vendas.", "warning")
    try:
        start_date, end_date = _filter_values()
    except ValueError as error:
        flash(str(error), "danger")
        start_date = end_date = None
    headers, rows = _report_data(report_type, start_date, end_date)
    if report_type == "vendas":
        summary = _summary(report_type, db.session.scalars(
            db.select(Sale).where(*_date_filters(start_date, end_date, Sale.created_at))
        ).all())
    elif report_type == "produtos":
        summary = _summary(report_type, db.session.scalars(
            db.select(Product).where(Product.is_active.is_(True), *_date_filters(start_date, end_date, Product.created_at))
        ).all())
    elif report_type == "estoque":
        summary_rows = db.session.execute(
            db.select(StockMovement, Product).join(Product).where(
                *_date_filters(start_date, end_date, StockMovement.created_at)
            )
        ).all()
        summary = _summary(report_type, summary_rows)
    else:
        summary = _summary(report_type, db.session.scalars(
            db.select(FinancialEntry).where(
                *_date_filters(start_date, end_date, FinancialEntry.occurred_at)
            )
        ).all())
    csv_url = url_for(
        "reports.export_csv",
        tipo=report_type,
        inicio=start_date.isoformat() if start_date else "",
        fim=end_date.isoformat() if end_date else "",
    )
    return render_template(
        "reports/index.html",
        reports=REPORTS,
        report_type=report_type,
        report_title=REPORTS[report_type],
        headers=headers,
        rows=rows,
        summary=summary,
        start_date=start_date.isoformat() if start_date else "",
        end_date=end_date.isoformat() if end_date else "",
        csv_url=csv_url,
    )


@reports.get("/exportar.csv")
def export_csv():
    report_type = request.args.get("tipo", "vendas")
    if report_type not in REPORTS:
        return "Tipo de relatório inválido.", 400
    try:
        start_date, end_date = _filter_values()
    except ValueError as error:
        return str(error), 400
    headers, rows = _report_data(report_type, start_date, end_date)
    csv_content = StringIO(newline="")
    writer = csv.writer(csv_content)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_safe_csv_value(value) for value in row])
    response = Response("\ufeff" + csv_content.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="relatorio-{report_type}.csv"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _safe_csv_value(value):
    rendered = str(value)
    if rendered.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + rendered
    return rendered
