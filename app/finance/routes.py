from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import uuid

from flask import flash, redirect, render_template, request, url_for
from app.extensions import db
from app.models import FinancialEntry, Sale, SaleItem
from app.finance import finance


BUSINESS_TZ = timezone(timedelta(hours=-3))


def _parse_filter_date(value: str, label: str):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Informe uma data válida para {label}.") from None


def _utc_boundary(day: date):
    local_midnight = datetime.combine(day, time.min, tzinfo=BUSINESS_TZ)
    return local_midnight.astimezone(timezone.utc)


def _entry_amount(value: str) -> Decimal:
    try:
        amount = Decimal(value.strip().replace(",", "."))
    except (AttributeError, InvalidOperation):
        raise ValueError("Informe um valor financeiro válido.") from None
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise ValueError("O valor deve ser maior que zero e ter até duas casas decimais.")
    return amount


@finance.get("/")
def index():
    try:
        start_date = _parse_filter_date(request.args.get("inicio", ""), "data inicial")
        end_date = _parse_filter_date(request.args.get("fim", ""), "data final")
        if start_date and end_date and start_date > end_date:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
    except ValueError as error:
        flash(str(error), "danger")
        start_date = end_date = None

    conditions = []
    if start_date:
        conditions.append(FinancialEntry.occurred_at >= _utc_boundary(start_date))
    if end_date:
        conditions.append(FinancialEntry.occurred_at < _utc_boundary(end_date + timedelta(days=1)))
    entries = db.session.scalars(
        db.select(FinancialEntry).where(*conditions).order_by(FinancialEntry.occurred_at.desc(), FinancialEntry.id.desc())
    ).all()
    revenue = sum((entry.amount for entry in entries if entry.kind == "receita"), Decimal("0.00"))
    expenses = sum((entry.amount for entry in entries if entry.kind == "despesa"), Decimal("0.00"))

    sale_conditions = []
    if start_date:
        sale_conditions.append(Sale.created_at >= _utc_boundary(start_date))
    if end_date:
        sale_conditions.append(Sale.created_at < _utc_boundary(end_date + timedelta(days=1)))
    sale_cost_rows = db.session.execute(
        db.select(SaleItem.unit_cost, SaleItem.quantity).join(Sale).where(*sale_conditions)
    ).all()
    cost_of_sales = sum((unit_cost * quantity for unit_cost, quantity in sale_cost_rows), Decimal("0.00"))

    return render_template(
        "finance/index.html",
        entries=entries,
        start_date=start_date.isoformat() if start_date else "",
        end_date=end_date.isoformat() if end_date else "",
        revenue=revenue,
        expenses=expenses,
        balance=revenue - expenses,
        estimated_profit=revenue - cost_of_sales - expenses,
        cost_of_sales=cost_of_sales,
    )


@finance.route("/novo", methods=["GET", "POST"])
def create():
    idempotency_key = str(uuid.uuid4())
    if request.method == "POST":
        try:
            idempotency_key = str(uuid.UUID(request.form.get("idempotency_key", "")))
            existing = db.session.scalar(
                db.select(FinancialEntry).where(FinancialEntry.idempotency_key == idempotency_key)
            )
            if existing:
                flash("Este lançamento já havia sido registrado.", "info")
                return redirect(url_for("finance.index"))

            kind = request.form.get("kind", "")
            if kind not in {"receita", "despesa"}:
                raise ValueError("Selecione receita ou despesa.")
            category = request.form.get("category", "").strip()
            description = request.form.get("description", "").strip()
            if not category or len(category) > 80:
                raise ValueError("Informe uma categoria com até 80 caracteres.")
            if not description or len(description) > 240:
                raise ValueError("Informe uma descrição com até 240 caracteres.")
            try:
                occurred_day = date.fromisoformat(request.form.get("occurred_on", ""))
            except ValueError:
                raise ValueError("Informe uma data válida para o lançamento.") from None

            entry = FinancialEntry(
                kind=kind,
                category=category,
                description=description,
                amount=_entry_amount(request.form.get("amount", "")),
                occurred_at=_utc_boundary(occurred_day),
                idempotency_key=idempotency_key,
            )
            db.session.add(entry)
            db.session.commit()
            flash("Lançamento financeiro registrado.", "success")
            return redirect(url_for("finance.index"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")

    today = datetime.now(BUSINESS_TZ).date().isoformat()
    return render_template("finance/form.html", idempotency_key=idempotency_key, today=today)
