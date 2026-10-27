from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.modules.directory.models.customer import Customer
from app.modules.directory.schemas.customer import CustomerCreate, CustomerUpdate


def list_customers(session: Session, user: User, search: str | None = None, limit: int = 50) -> list[Customer]:
    query = select(Customer).where(Customer.company_id == user.company_id, Customer.is_active.is_(True)).order_by(Customer.name).limit(limit)
    if search and search.strip():
        query = query.where(Customer.name.ilike(f"%{search.strip()}%"))
    return list(session.scalars(query).all())


def create_customer(session: Session, user: User, data: CustomerCreate) -> Customer:
    customer = Customer(id=uuid4(), company_id=user.company_id, **data.model_dump())
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


def update_customer(session: Session, user: User, customer_id: UUID, data: CustomerUpdate) -> Customer:
    customer = session.scalar(select(Customer).where(Customer.id == customer_id, Customer.company_id == user.company_id))
    if customer is None:
        raise HTTPException(404, "Cliente no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    session.commit()
    session.refresh(customer)
    return customer
