"""Settings endpoints. Secrets are never returned."""

from __future__ import annotations

from app.database.session import get_db
from app.schemas import SettingsOut, SettingsUpdate
from app.services.settings_service import get_settings_view, save_runtime_config
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(tags=["settings"])


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return get_settings_view(db)


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    save_runtime_config(db, payload)
    return get_settings_view(db)
