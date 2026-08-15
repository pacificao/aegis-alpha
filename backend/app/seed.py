from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BrokerConnectionConfig, Phase, Task, TaskStatus
from .roadmap_data import PHASES

PHASE1_COMPLETE = {
    3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 21, 22, 23, 24, 25,
    26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 39, 40, 41, 42, 44, 45, 46,
    48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
    66, 67, 68, 69,
}
PHASE1_BLOCKED = {4, 37, 38, 43, 47}


def seed_roadmap(db: Session) -> None:
    broker = db.scalar(select(BrokerConnectionConfig).where(BrokerConnectionConfig.provider == "robinhood"))
    if broker is None:
        db.add(BrokerConnectionConfig(provider="robinhood", connection_name="Robinhood Agentic", endpoint="https://agent.robinhood.com/mcp/trading", mode="READ_ONLY"))
    for number, name, description, tasks in PHASES:
        phase = db.scalar(select(Phase).where(Phase.number == number))
        if phase is None:
            phase = Phase(number=number, name=name, description=description)
            db.add(phase)
            db.flush()
        for ordinal, title in enumerate(tasks, 1):
            existing = db.scalar(select(Task).where(Task.phase_id == phase.id, Task.ordinal == ordinal))
            if existing is None:
                initial_status = TaskStatus.NOT_STARTED
                notes = ""
                if number == 1 and ordinal in PHASE1_COMPLETE:
                    initial_status = TaskStatus.COMPLETE
                elif number == 1 and ordinal in PHASE1_BLOCKED:
                    initial_status = TaskStatus.BLOCKED
                    notes = "Host prerequisite or privileged verification required; see development status."
                elif number == 1:
                    initial_status = TaskStatus.IN_PROGRESS
                db.add(Task(phase_id=phase.id, ordinal=ordinal, title=title, status=initial_status, notes=notes))
    db.commit()
