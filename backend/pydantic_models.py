from pydantic import BaseModel
from typing import List

class CartItemCreate(BaseModel):
    # product_name: str
    # quantity: int
    # price: int
    product_id: int  # required to fetch product details from DB
    quantity: int

class CartResponse(BaseModel):
    id: int
    cashier_id: int
    is_checked_out: bool

    class Config:
        orm_mode = True

class CartItemResponse(BaseModel):
    id: int
    product_name: str
    quantity: int
    price: int

    class Config:
        orm_mode = True

