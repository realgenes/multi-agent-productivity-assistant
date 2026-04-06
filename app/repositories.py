from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from dateutil import parser

from app import models, schemas


class DuplicateError(Exception):
    """Raised when a record with the same key fields already exists."""
    pass


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: schemas.TaskCreate) -> models.TaskRecord:
        due_date = payload.due_date

        if isinstance(due_date, str):
            try:
                due_date = parser.parse(due_date, fuzzy=True)
            except Exception:
                due_date = None

        existing = self.db.query(models.TaskRecord).filter(
            func.lower(models.TaskRecord.title) == payload.title.lower().strip(),
            models.TaskRecord.due_date == due_date
        ).first()

        if existing:
            raise DuplicateError(f"Task '{payload.title.strip()}' already exists.")

        record = models.TaskRecord(
            title=payload.title.strip(),
            description=payload.description,
            due_date=due_date,
        )

        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            return record
        except IntegrityError:
            self.db.rollback()
            raise DuplicateError(f"Task '{payload.title.strip()}' already exists.")

    def complete(self, task_id: int) -> bool:
        record = self.db.query(models.TaskRecord).filter(models.TaskRecord.id == task_id).first()
        if not record:
            return False
        record.status = "completed"
        self.db.commit()
        return True

    def delete_by_title(self, title: str) -> bool:
        record = self.db.query(models.TaskRecord).filter(
            func.lower(models.TaskRecord.title) == title.lower().strip()
        ).first()
        if not record:
            return False
        self.db.delete(record)
        self.db.commit()
        return True

    def delete_by_id(self, task_id: int) -> bool:
        record = self.db.query(models.TaskRecord).filter(models.TaskRecord.id == task_id).first()
        if not record:
            return False
        self.db.delete(record)
        self.db.commit()
        return True

    def delete_all(self) -> int:
        count = self.db.query(models.TaskRecord).delete()
        self.db.commit()
        return count

    def list_all(self) -> list[models.TaskRecord]:
        return self.db.query(models.TaskRecord).order_by(
            models.TaskRecord.created_at.desc()
        ).all()


class NoteRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: schemas.NoteCreate) -> models.NoteRecord:
        existing = self.db.query(models.NoteRecord).filter(
            func.lower(models.NoteRecord.title) == payload.title.lower().strip()
        ).first()
        if existing:
            raise DuplicateError(f"Note '{payload.title.strip()}' already exists.")

        record = models.NoteRecord(
            title=payload.title.strip(),
            content=payload.content
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete_by_title(self, title: str) -> bool:
        record = self.db.query(models.NoteRecord).filter(
            func.lower(models.NoteRecord.title) == title.lower().strip()
        ).first()
        if not record:
            return False
        self.db.delete(record)
        self.db.commit()
        return True

    def delete_by_id(self, note_id: int) -> bool:
        record = self.db.query(models.NoteRecord).filter(models.NoteRecord.id == note_id).first()
        if not record:
            return False
        self.db.delete(record)
        self.db.commit()
        return True

    def delete_all(self) -> int:
        count = self.db.query(models.NoteRecord).delete()
        self.db.commit()
        return count

    def list_all(self) -> list[models.NoteRecord]:
        return self.db.query(models.NoteRecord).order_by(
            models.NoteRecord.created_at.desc()
        ).all()


class WorkflowRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_message: str, plan: str, outcome: str) -> models.WorkflowRecord:
        record = models.WorkflowRecord(
            user_message=user_message,
            plan=plan,
            outcome=outcome
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

