import re

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.customers import customers
from app.extensions import db
from app.models import Customer


def _customer_form_data(form):
    name = form.get("name", "").strip()
    phone = form.get("phone", "").strip()
    normalized_phone = re.sub(r"\D", "", phone)
    email = form.get("email", "").strip().lower()
    notes = form.get("notes", "").strip()

    if not name or len(name) > 120:
        raise ValueError("Informe o nome do cliente (até 120 caracteres).")
    if not 10 <= len(normalized_phone) <= 13:
        raise ValueError("Informe um telefone brasileiro com DDD.")
    if not re.fullmatch(r"[+()\d\s.-]+", phone):
        raise ValueError("Use apenas números e símbolos comuns de telefone.")
    if len(phone) > 30:
        raise ValueError("O telefone deve ter até 30 caracteres.")
    if email and (len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)):
        raise ValueError("Informe um e-mail válido.")
    if len(notes) > 2000:
        raise ValueError("As observações devem ter até 2.000 caracteres.")
    return {"name": name, "phone": phone, "normalized_phone": normalized_phone, "email": email, "notes": notes}


def _active_customer(customer_id):
    return db.first_or_404(
        db.select(Customer).where(Customer.id == customer_id, Customer.is_active.is_(True)),
        description="Cliente não encontrado.",
    )


@customers.get("/")
def index():
    query = request.args.get("q", "").strip()
    statement = db.select(Customer).where(Customer.is_active.is_(True))
    if query:
        pattern = f"%{query}%"
        digits = re.sub(r"\D", "", query)
        conditions = [Customer.name.ilike(pattern), Customer.phone.ilike(pattern), Customer.email.ilike(pattern)]
        if digits:
            conditions.append(Customer.normalized_phone.contains(digits))
        statement = statement.where(or_(*conditions))
    items = db.session.scalars(statement.order_by(Customer.name)).all()
    return render_template("customers/index.html", customers=items, query=query)


@customers.route("/novo", methods=["GET", "POST"])
def create():
    values = request.form if request.method == "POST" else {}
    if request.method == "POST":
        try:
            customer = Customer(**_customer_form_data(request.form))
            db.session.add(customer)
            db.session.commit()
            flash("Cliente cadastrado com sucesso.", "success")
            return redirect(url_for("customers.detail", customer_id=customer.id))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um cliente cadastrado com esse telefone.", "danger")
    return render_template("customers/form.html", customer=None, values=values, title="Cadastrar cliente")


@customers.get("/<int:customer_id>")
def detail(customer_id):
    customer = _active_customer(customer_id)
    return render_template("customers/detail.html", customer=customer)


@customers.route("/<int:customer_id>/editar", methods=["GET", "POST"])
def edit(customer_id):
    customer = _active_customer(customer_id)
    values = request.form if request.method == "POST" else {}
    if request.method == "POST":
        try:
            data = _customer_form_data(request.form)
            duplicate = db.session.scalar(
                db.select(Customer.id).where(
                    Customer.normalized_phone == data["normalized_phone"],
                    Customer.id != customer.id,
                    Customer.is_active.is_(True),
                )
            )
            if duplicate:
                raise ValueError("Já existe outro cliente cadastrado com esse telefone.")
            for field, value in data.items():
                setattr(customer, field, value)
            db.session.commit()
            flash("Cadastro do cliente atualizado.", "success")
            return redirect(url_for("customers.detail", customer_id=customer.id))
        except (ValueError, IntegrityError) as error:
            db.session.rollback()
            message = str(error) if isinstance(error, ValueError) else "Já existe um cliente cadastrado com esse telefone."
            flash(message, "danger")
            customer = _active_customer(customer_id)
    return render_template("customers/form.html", customer=customer, values=values, title="Editar cliente")


@customers.route("/<int:customer_id>/excluir", methods=["GET", "POST"])
def deactivate(customer_id):
    customer = _active_customer(customer_id)
    if request.method == "POST":
        customer.is_active = False
        db.session.commit()
        flash("Cliente removido da lista. O histórico relacionado será preservado.", "success")
        return redirect(url_for("customers.index"))
    return render_template("customers/confirm_delete.html", customer=customer)
