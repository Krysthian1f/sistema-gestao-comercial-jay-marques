from flask import Blueprint

finance = Blueprint("finance", __name__, url_prefix="/finance")

from app.finance import routes  # noqa: E402,F401
