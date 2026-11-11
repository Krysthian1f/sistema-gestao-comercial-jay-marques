from datetime import datetime, timedelta, timezone

from flask import render_template

from app.dashboard import dashboard


@dashboard.get("/")
def index():
    brasilia = timezone(timedelta(hours=-3))
    today = datetime.now(brasilia).strftime("%d/%m/%Y")
    return render_template("dashboard/index.html", today=today)
