from datetime import datetime, timedelta, timezone
import secrets

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import auth
from app.extensions import db
from app.models import User


_DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_urlsafe(32))


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        user = db.session.scalar(db.select(User).where(User.username == username)) if username else None
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        locked = user is not None and user.locked_until is not None and user.locked_until > now
        valid_password = check_password_hash(
            user.password_hash if user is not None else _DUMMY_PASSWORD_HASH,
            password,
        )

        if user is not None and user.is_active and user.is_admin and not locked and valid_password:
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login_at = now
            db.session.commit()
            session.clear()
            session.permanent = True
            login_user(user, remember=False, fresh=True)
            flash("Acesso realizado. Boas-vindas!", "success")
            return redirect(url_for("dashboard.index"))

        if user is not None and user.is_active and not locked:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= current_app.config["MAX_LOGIN_ATTEMPTS"]:
                user.locked_until = now + timedelta(minutes=current_app.config["LOGIN_LOCKOUT_MINUTES"])
                db.session.commit()
                flash("Muitas tentativas. O acesso foi temporariamente bloqueado por 15 minutos.", "danger")
            else:
                db.session.commit()
                flash("Usuário ou senha incorretos.", "danger")
        elif locked:
            flash("Muitas tentativas. Aguarde o fim do bloqueio temporário para tentar novamente.", "danger")
        else:
            flash("Usuário ou senha incorretos.", "danger")

    return render_template("auth/login.html")


@auth.post("/sair")
def logout():
    logout_user()
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("auth.login"))
