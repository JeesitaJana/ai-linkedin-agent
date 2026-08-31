"""Single-process scheduler and safe internal workflow trigger."""

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import Lock
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models.schedule import Schedule
from app.services.schedules import get_schedules

logger = logging.getLogger(__name__)
APSCHEDULER_WEEKDAYS = {
    "monday": "mon", "tuesday": "tue", "wednesday": "wed", "thursday": "thu",
    "friday": "fri", "saturday": "sat", "sunday": "sun",
}


@dataclass(frozen=True)
class WorkflowExecution:
    schedule_id: int
    schedule_name: str
    topics: list[str]
    triggered_at: datetime
    trigger: str


class ScheduleScheduler:
    """Owns APScheduler state; no HTTP endpoint exposes manual execution."""

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._session_factory = session_factory
        self._events: list[WorkflowExecution] = []
        self._started = False
        self._lock = Lock()

    @staticmethod
    def job_id(schedule_id: int) -> str:
        return f"schedule:{schedule_id}"

    def start(self) -> None:
        with self._lock:
            if not self._started:
                self._scheduler.start()
                self._started = True
        self.reload_active_schedules()

    def shutdown(self) -> None:
        with self._lock:
            if self._started:
                self._scheduler.shutdown(wait=False)
                self._started = False

    def reload_active_schedules(self) -> None:
        if self._session_factory is None:
            return
        try:
            with self._session_factory() as db:
                schedules = get_schedules(db, active_only=True)
                active_ids = {schedule.id for schedule in schedules}
                for job in self._scheduler.get_jobs():
                    if job.id.startswith("schedule:") and int(job.id.split(":", 1)[1]) not in active_ids:
                        self._scheduler.remove_job(job.id)
                for schedule in schedules:
                    self.register(schedule)
        except SQLAlchemyError:
            # A migration/database outage should not prevent FastAPI from serving health.
            logger.exception("Could not load active schedules")

    def register(self, schedule: Schedule) -> None:
        job_id = self.job_id(schedule.id)
        if not schedule.active:
            if self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)
            return
        trigger = CronTrigger(
            day_of_week=",".join(APSCHEDULER_WEEKDAYS[day] for day in schedule.days),
            hour=schedule.time.hour,
            minute=schedule.time.minute,
            timezone=ZoneInfo(schedule.timezone),
        )
        self._scheduler.add_job(
            self.run_schedule_now,
            trigger=trigger,
            id=job_id,
            args=[schedule.id],
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    def remove(self, schedule_id: int) -> None:
        job_id = self.job_id(schedule_id)
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

    def run_schedule_now(self, schedule_id: int) -> WorkflowExecution | None:
        """Internal development/test hook; validates active state before triggering."""
        if self._session_factory is None:
            return None
        with self._session_factory() as db:
            schedule = db.get(Schedule, schedule_id)
            if schedule is None or not schedule.active:
                return None
            event = WorkflowExecution(
                schedule_id=schedule.id,
                schedule_name=schedule.name,
                topics=list(schedule.topics),
                triggered_at=datetime.now(UTC),
                trigger="schedule",
            )
        self._events.append(event)
        logger.info("Content workflow triggered for schedule %s", schedule_id)
        return event

    @property
    def events(self) -> list[dict[str, object]]:
        return [asdict(event) for event in self._events]


_scheduler: ScheduleScheduler | None = None


def get_scheduler(session_factory: sessionmaker[Session] | None = None) -> ScheduleScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = ScheduleScheduler(session_factory)
    elif session_factory is not None and _scheduler._session_factory is None:
        _scheduler._session_factory = session_factory
    return _scheduler
