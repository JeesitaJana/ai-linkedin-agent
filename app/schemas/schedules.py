"""Pydantic schemas and validation for recurring schedules."""

from datetime import datetime, time as time_type
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _validate_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("name must not be empty")
    return value


def _validate_days(value: list[str]) -> list[str]:
    if not value:
        raise ValueError("at least one day is required")
    normalized = [day.strip().lower() for day in value]
    if any(day not in WEEKDAYS for day in normalized):
        raise ValueError("days must contain valid weekday names")
    if len(set(normalized)) != len(normalized):
        raise ValueError("days must not contain duplicates")
    return normalized


def _validate_topics(value: list[str]) -> list[str]:
    if not value:
        raise ValueError("at least one topic is required")
    normalized = [topic.strip() for topic in value]
    if any(not topic for topic in normalized):
        raise ValueError("topics must not contain empty values")
    if len({topic.casefold() for topic in normalized}) != len(normalized):
        raise ValueError("topics must not contain duplicates")
    return normalized


def _validate_time(value: time_type) -> time_type:
    if value.second or value.microsecond or value.tzinfo is not None:
        raise ValueError("time must use HH:MM 24-hour representation")
    return value


class _ScheduleFields(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    days: list[str] = Field(min_length=1)
    time: time_type
    timezone: str = Field(min_length=1, max_length=64)
    topics: list[str] = Field(min_length=1, max_length=50)
    active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_name(value)

    @field_validator("days")
    @classmethod
    def validate_days(cls, value: list[str]) -> list[str]:
        return _validate_days(value)

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: time_type) -> time_type:
        return _validate_time(value)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, value: list[str]) -> list[str]:
        return _validate_topics(value)


class ScheduleCreate(_ScheduleFields):
    pass


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    days: list[str] | None = Field(default=None, min_length=1)
    time: time_type | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    topics: list[str] | None = Field(default=None, min_length=1, max_length=50)
    active: bool | None = None

    _name = field_validator("name")(_validate_name)
    _days = field_validator("days")(_validate_days)
    _topics = field_validator("topics")(_validate_topics)
    _time = field_validator("time")(_validate_time)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class ScheduleResponse(_ScheduleFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("time")
    def serialize_time(self, value: time_type) -> str:
        return value.strftime("%H:%M")
