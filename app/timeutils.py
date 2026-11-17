from datetime import datetime, timedelta, timezone


BRASILIA_TZ = timezone(timedelta(hours=-3))


def to_brasilia(value: datetime) -> datetime:
    """Interpreta horários sem fuso do banco como UTC e aplica o fuso comercial."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BRASILIA_TZ)


def format_brasilia_datetime(value: datetime) -> str:
    return to_brasilia(value).strftime("%d/%m/%Y %H:%M")


def format_brasilia_date(value: datetime) -> str:
    return to_brasilia(value).strftime("%d/%m/%Y")
