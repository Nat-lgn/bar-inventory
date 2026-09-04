from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False)
    density = Column(Float, default=1.0)
    tare_weight = Column(Float, default=0.0)

class InventoryRecord(Base):
    __tablename__ = "inventory_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    current_weight = Column(Float, default=0.0)
    checked_at = Column(DateTime)
