from flask import Blueprint

products = Blueprint("products", __name__, url_prefix="/products")

from app.products import routes  # noqa: E402,F401
