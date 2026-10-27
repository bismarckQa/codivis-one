import pytest
from pydantic import ValidationError

from app.modules.directory.schemas.customer import CustomerCreate, CustomerUpdate


def test_customer_create_normalizes_name_and_email():
    customer = CustomerCreate(name="  María  López ", email=" MARIA@EXAMPLE.COM ")
    assert customer.name == "María López"
    assert customer.email == "maria@example.com"


def test_customer_create_requires_a_name():
    with pytest.raises(ValidationError):
        CustomerCreate(name="   ")


def test_customer_update_requires_at_least_one_change():
    with pytest.raises(ValidationError):
        CustomerUpdate()
