from datetime import time

from sqlalchemy import inspect

from app.models.schedule import Schedule
from app.services.scheduler import ScheduleScheduler


def payload(**changes):
    value = {"name": "LinkedIn AI Content", "days": ["monday", "wednesday", "friday"], "time": "18:00", "timezone": "Asia/Kolkata", "topics": ["Health Tech", "Artificial Intelligence"], "active": True}
    value.update(changes)
    return value


def create(client, **changes):
    response = client.post("/schedules", json=payload(**changes))
    assert response.status_code == 201
    return response.json()


def test_schedule_crud_and_persistence(client, db_session):
    created = create(client)
    assert created["time"] == "18:00"
    assert client.get("/schedules").json() == [created]
    assert client.get(f"/schedules/{created['id']}").json()["name"] == "LinkedIn AI Content"
    updated = client.put(f"/schedules/{created['id']}", json={"active": False, "name": "Paused"})
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    persisted = db_session.get(Schedule, created["id"])
    assert persisted is not None and persisted.name == "Paused" and persisted.active is False
    assert client.delete(f"/schedules/{created['id']}").status_code == 204
    assert client.get(f"/schedules/{created['id']}").status_code == 404


def test_schedule_validation(client):
    for changes in (
        {"name": " "}, {"days": []}, {"days": ["monday", "monday"]}, {"days": ["funday"]},
        {"time": "25:00"}, {"time": "18:00:01"}, {"timezone": "Not/AZone"},
        {"topics": []}, {"topics": [" "]}, {"topics": ["AI", "ai"]},
    ):
        assert client.post("/schedules", json=payload(**changes)).status_code == 422


def test_missing_schedule_and_inactive_schedule(client, scheduler):
    assert client.get("/schedules/999").status_code == 404
    inactive = create(client, active=False)
    assert scheduler.run_schedule_now(inactive["id"]) is None


def test_scheduler_registration_and_safe_internal_trigger(db_session, scheduler):
    schedule = Schedule(**payload(time=time(18, 0)))
    db_session.add(schedule)
    db_session.commit()
    scheduler.register(schedule)
    assert scheduler._scheduler.get_job(ScheduleScheduler.job_id(schedule.id)) is not None
    event = scheduler.run_schedule_now(schedule.id)
    assert event is not None
    assert event.schedule_id == schedule.id
    assert event.topics == schedule.topics
    schedule.active = False
    db_session.commit()
    assert scheduler.run_schedule_now(schedule.id) is None


def test_scheduler_startup_loads_only_active_schedules(db_session):
    active = Schedule(**payload(time=time(18, 0)))
    inactive = Schedule(**payload(name="Paused", active=False, time=time(19, 0)))
    db_session.add_all([active, inactive])
    db_session.commit()
    from sqlalchemy.orm import sessionmaker
    loaded_scheduler = ScheduleScheduler(sessionmaker(bind=db_session.bind, autoflush=False, expire_on_commit=False))
    try:
        loaded_scheduler.start()
        assert loaded_scheduler._scheduler.get_job(ScheduleScheduler.job_id(active.id)) is not None
        assert loaded_scheduler._scheduler.get_job(ScheduleScheduler.job_id(inactive.id)) is None
    finally:
        loaded_scheduler.shutdown()


def test_schedule_table_is_in_metadata(db_session):
    assert "schedules" in inspect(db_session.bind).get_table_names()
