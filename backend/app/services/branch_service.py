from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Branch, Company, License, User
from app.schemas.branch import BranchCreate, BranchUpdate


def list_branches(session: Session, user: User) -> list[Branch]:
    return list(session.scalars(select(Branch).where(Branch.company_id == user.company_id).order_by(Branch.name)).all())


def create_branch(session: Session, user: User, data: BranchCreate) -> Branch:
    company = session.scalar(select(Company).where(Company.id == user.company_id).with_for_update())
    if company is None:
        raise HTTPException(404, "Empresa no encontrada")
    license_row = session.scalar(select(License).where(License.company_id == user.company_id).order_by(License.created_at.desc()).limit(1))
    if license_row is None:
        raise HTTPException(409, "La instalación no tiene licencia activa")
    count = session.scalar(select(func.count(Branch.id)).where(Branch.company_id == user.company_id)) or 0
    if count >= license_row.max_branches:
        raise HTTPException(409, "Se alcanzó el límite de sucursales de la licencia")
    duplicate = session.scalar(select(Branch).where(Branch.company_id == user.company_id, func.lower(Branch.name) == data.name.lower()))
    if duplicate:
        raise HTTPException(409, "Ya existe una sucursal con ese nombre")
    branch = Branch(id=uuid4(), company_id=user.company_id, name=data.name)
    session.add(branch)
    session.commit()
    session.refresh(branch)
    return branch


def update_branch(session: Session, user: User, branch_id: UUID, data: BranchUpdate) -> Branch:
    branch = session.scalar(select(Branch).where(Branch.id == branch_id, Branch.company_id == user.company_id))
    if branch is None:
        raise HTTPException(404, "Sucursal no encontrada")
    if data.name and session.scalar(select(Branch).where(Branch.company_id == user.company_id, Branch.id != branch_id, func.lower(Branch.name) == data.name.lower())):
        raise HTTPException(409, "Ya existe una sucursal con ese nombre")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    session.commit()
    session.refresh(branch)
    return branch
