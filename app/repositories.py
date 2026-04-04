from sqlalchemy.orm import Session

from app import models, schemas


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: schemas.TaskCreate) -> models.TaskRecord:
        record = models.TaskRecord(
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_all(self) -> list[models.TaskRecord]:
        return self.db.query(models.TaskRecord).order_by(models.TaskRecord.created_at.desc()).all()


class NoteRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: schemas.NoteCreate) -> models.NoteRecord:
        record = models.NoteRecord(title=payload.title, content=payload.content)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_all(self) -> list[models.NoteRecord]:
        return self.db.query(models.NoteRecord).order_by(models.NoteRecord.created_at.desc()).all()


class WorkflowRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_message: str, plan: str, outcome: str) -> models.WorkflowRecord:
        record = models.WorkflowRecord(user_message=user_message, plan=plan, outcome=outcome)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
