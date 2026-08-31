"""Database-backed schedule operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.schemas.schedules import ScheduleCreate, ScheduleUpdate


class ScheduleNotFoundError(Exception):
    """Raised when a schedule is not present."""


def _get_or_raise(db: Session, schedule_id: int) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise ScheduleNotFoundError("Schedule not found")
    return schedule


def create_schedule(db: Session, payload: ScheduleCreate) -> Schedule:
    schedule = Schedule(**payload.model_dump())
    db.add(schedule)
    db.flush()
    db.refresh(schedule)
    return schedule


def get_schedules(db: Session, *, active_only: bool = False) -> list[Schedule]:
    statement = select(Schedule).order_by(Schedule.id)
    if active_only:
        statement = statement.where(Schedule.active.is_(True))
    return list(db.scalars(statement).all())


def get_schedule(db: Session, schedule_id: int) -> Schedule:
    return _get_or_raise(db, schedule_id)


def update_schedule(db: Session, schedule_id: int, payload: ScheduleUpdate) -> Schedule:
    schedule = _get_or_raise(db, schedule_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)
    db.flush()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule_id: int) -> None:
    db.delete(_get_or_raise(db, schedule_id))
    db.flush()
