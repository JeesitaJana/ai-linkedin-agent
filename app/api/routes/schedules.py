"""Schedule configuration API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.schedules import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from app.services import schedules as schedule_service
from app.services.scheduler import get_scheduler
from app.services.schedules import ScheduleNotFoundError

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
not_found_response = {404: {"description": "Schedule not found"}}


def _not_found() -> None:
    raise HTTPException(status_code=404, detail="Schedule not found")


def _database_error(exc: SQLAlchemyError) -> None:
    raise HTTPException(status_code=500, detail="Database operation failed") from exc


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleCreate, db: DbSession):
    try:
        schedule = schedule_service.create_schedule(db, payload)
        get_scheduler().register(schedule)
        return schedule
    except SQLAlchemyError as exc:
        _database_error(exc)


@router.get("/schedules", response_model=list[ScheduleResponse])
def list_schedules(db: DbSession):
    try:
        return schedule_service.get_schedules(db)
    except SQLAlchemyError as exc:
        _database_error(exc)


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse, responses=not_found_response)
def get_schedule(schedule_id: int, db: DbSession):
    try:
        return schedule_service.get_schedule(db, schedule_id)
    except ScheduleNotFoundError:
        _not_found()
    except SQLAlchemyError as exc:
        _database_error(exc)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse, responses=not_found_response)
def update_schedule(schedule_id: int, payload: ScheduleUpdate, db: DbSession):
    try:
        schedule = schedule_service.update_schedule(db, schedule_id, payload)
        get_scheduler().register(schedule)
        return schedule
    except ScheduleNotFoundError:
        _not_found()
    except SQLAlchemyError as exc:
        _database_error(exc)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT, responses=not_found_response)
def delete_schedule(schedule_id: int, db: DbSession):
    try:
        schedule_service.delete_schedule(db, schedule_id)
        get_scheduler().remove(schedule_id)
    except ScheduleNotFoundError:
        _not_found()
    except SQLAlchemyError as exc:
        _database_error(exc)
