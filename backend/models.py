from sqlalchemy import Column, Float, Integer, String, ForeignKey, DateTime, Boolean
from database import Base
from sqlalchemy.orm import relationship
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

class Server(Base):
    __tablename__ = "server"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))              
    email = Column(String(255), unique=True, index=True)  
    password = Column(String(255))          
    gender = Column(String(20))    
    role = Column(String(20))

class Cashier(Base):
    __tablename__ = "cashier"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))              
    email = Column(String(255), unique=True, index=True)  
    password = Column(String(255))          
    gender = Column(String(20))
    role = Column(String(20))

class PasswordHistory(Base):
    __tablename__ = "password_history"
    id = Column(Integer, primary_key=True, index=True)    
    server_id = Column(Integer, ForeignKey("server.id"), nullable=True)
    cashier_id = Column(Integer, ForeignKey("cashier.id"), nullable=True)
    hashed_password = Column(String(255))
    changed_at = Column(DateTime, default=datetime.now(IST))
    server = relationship("Server", backref="passwords")
    cashier = relationship("Cashier", backref="passwords")

class Cart(Base):
    __tablename__ = "cart"
    id = Column(Integer, primary_key=True, index=True)
    cashier_id = Column(Integer, ForeignKey("cashier.id"), nullable=False)
    is_checked_out = Column(Boolean, default=False)
    channel = Column(String(50), default="Dine-In")
    subtotal = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    checked_out_at = Column(DateTime, default=None)
    round_off_amount = Column(Float, nullable=True)
    payment_method = Column(String, nullable=True)
    rounded_total = Column(Float, nullable=True)
    cash_received = Column(Float, nullable=True)
    change_returned = Column(Float, nullable=True)
    discount_applied = Column(String(100), nullable=True)
    discount_amount = Column(Float, default=0.0)
    receipt_number = Column(String(50), unique=True, index=True, nullable=True)
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    deals = relationship("CartDeal", backref="cart", cascade="all, delete-orphan")
    total_paid = Column(Float, default=0.0)
    change_returned = Column(Float, default=0.0)
    
    
class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("cart.id"), nullable=False)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)
    cart = relationship("Cart", back_populates="items")
    is_voided = Column(Boolean, default=False) #newwwwwwwwwwwww
    product_id = Column(Integer, ForeignKey("products.id"))  # New foreign key

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    price = Column(Float, nullable=False)
    active = Column(Boolean, default=True)

class Discount(Base):
    __tablename__ = "discounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    min_order_value = Column(Float)
    max_discount = Column(Float)
    product_name = Column(String(100))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    active = Column(Boolean, default=True)

class Deal(Base):
    __tablename__ = "deals"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    editable = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    items = relationship("DealItem", back_populates="deal", cascade="all, delete-orphan")

class DealItem(Base):
    __tablename__ = "deal_items"
    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deals.id"))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product = relationship("Product")
    required = Column(Boolean, default=True)
    quantity = Column(Integer, default=1)
    deal = relationship("Deal", back_populates="items")
    modifiers = relationship("DealItemModifier", back_populates="deal_item", cascade="all, delete-orphan")

class Modifier(Base):
    __tablename__ = "modifiers"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price_diff = Column(Float, default=0.0)
    for_product_id = Column(Integer, ForeignKey("products.id"), nullable=True)

class DealItemModifier(Base):
    __tablename__ = "deal_item_modifiers"
    id = Column(Integer, primary_key=True)
    deal_item_id = Column(Integer, ForeignKey("deal_items.id"))
    modifier_id = Column(Integer, ForeignKey("modifiers.id"))
    deal_item = relationship("DealItem", back_populates="modifiers")
    modifier = relationship("Modifier")

class CartDeal(Base):
    __tablename__ = "cart_deals"
    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("cart.id"))
    deal_id = Column(Integer, ForeignKey("deals.id"))
    deal_name = Column(String(100))
    total_price = Column(Float, default=0.0)
    deal = relationship("Deal")
    items = relationship("CartDealItem", back_populates="cart_deal", cascade="all, delete-orphan")
    is_voided = Column(Boolean, default=False)

class CartDealItem(Base):
    __tablename__ = "cart_deal_items"
    id = Column(Integer, primary_key=True)
    cart_deal_id = Column(Integer, ForeignKey("cart_deals.id"))
    original_deal_item_id = Column(Integer, ForeignKey("deal_items.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    product_name = Column(String(255))
    quantity = Column(Integer, default=1)
    price = Column(Float, default=0.0)
    cart_deal = relationship("CartDeal", back_populates="items")
    product = relationship("Product")
    modifiers = relationship("CartDealItemModifier", back_populates="cart_deal_item", cascade="all, delete-orphan")
    is_voided = Column(Boolean, default=False)

class CartDealItemModifier(Base):
    __tablename__ = "cart_deal_item_modifiers"
    id = Column(Integer, primary_key=True)
    cart_deal_item_id = Column(Integer, ForeignKey("cart_deal_items.id"))
    modifier_id = Column(Integer, ForeignKey("modifiers.id"))
    modifier_name = Column(String(100))
    price_diff = Column(Float, default=0.0)
    cart_deal_item = relationship("CartDealItem", back_populates="modifiers")
    modifier = relationship("Modifier")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("cart.id"))
    method = Column(String(50))  # e.g., 'cash', 'upi', 'card'
    amount = Column(Float, nullable=False)
    is_tender = Column(Boolean, default=True)  # Flag to indicate actual tendered payment (vs internal adjustment, etc.)
    cart = relationship("Cart", backref="payments")


