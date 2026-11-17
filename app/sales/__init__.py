from flask import Blueprint

sales = Blueprint("sales", __name__, url_prefix="/sales")

from app.sales import routes  # noqa: E402,F401
