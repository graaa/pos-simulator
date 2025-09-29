"""
FastAPI backend for BAC-style POS demo
- No PAN/CVV/expiry handled by the POS
- POS only sends amount to terminal and stores masked data
Run local: uvicorn app.main:app --reload --port 8000
"""
from datetime import datetime, date
from typing import List, Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, DateTime, Float, JSON, create_engine, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from random import random, choice

# ----------------------------
# CORS (allow frontend dev server)
# ----------------------------
app = FastAPI(title="Demo POS (BAC-ready style)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://64.227.83.209:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Database setup
# ----------------------------
SQLALCHEMY_DATABASE_URL = "sqlite:////tmp/pos.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ItemModel(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    description = Column(String, nullable=True)
    active = Column(String, nullable=False, default="true")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class OrderModel(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    table = Column(String, nullable=True)
    items = Column(JSON, nullable=False)  # [{name, qty, price}] 
    subtotal = Column(Float, nullable=False)
    tip = Column(Float, nullable=False, default=0.0)
    total = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="OPEN")  # OPEN | PAID | VOID

    transactions = relationship("TxnModel", back_populates="order")

class TxnModel(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)

    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="CRC")

    status = Column(String, nullable=False)  # approved | declined | reversed
    auth_code = Column(String, nullable=True)
    masked_card = Column(String, nullable=True)  # **** **** **** 4242

    terminal_ref = Column(String, nullable=True)  # terminal transaction id
    terminal_meta = Column(JSON, nullable=True)   # additional non-sensitive info

    order = relationship("OrderModel", back_populates="transactions")

Base.metadata.create_all(bind=engine)

# ----------------------------
# Initialize dummy restaurant data
# ----------------------------
def init_restaurant_data():
    db: Session = next(get_db())
    
    # Check if items already exist
    if db.query(ItemModel).count() > 0:
        return
    
    # Costa Rican restaurant menu items
    restaurant_items = [
        # Appetizers
        {"name": "Ceviche de Pescado", "price": 4500, "category": "Appetizers", "description": "Fresh fish ceviche with lime and cilantro"},
        {"name": "Patacones", "price": 2800, "category": "Appetizers", "description": "Fried plantain slices with refried beans"},
        {"name": "Empanadas de Carne", "price": 2200, "category": "Appetizers", "description": "Beef empanadas with chimichurri sauce"},
        
        # Main Dishes
        {"name": "Casado", "price": 5500, "category": "Main Dishes", "description": "Traditional plate with rice, beans, meat, and salad"},
        {"name": "Gallo Pinto", "price": 3200, "category": "Main Dishes", "description": "Rice and beans with eggs and plantains"},
        {"name": "Arroz con Pollo", "price": 4800, "category": "Main Dishes", "description": "Chicken and rice with vegetables"},
        {"name": "Pescado Frito", "price": 6200, "category": "Main Dishes", "description": "Fried whole fish with rice and salad"},
        {"name": "Chifrijo", "price": 4200, "category": "Main Dishes", "description": "Rice, beans, pork, and pico de gallo"},
        
        # Beverages
        {"name": "Cerveza Imperial", "price": 1800, "category": "Beverages", "description": "Local Costa Rican beer"},
        {"name": "Cerveza Pilsen", "price": 1800, "category": "Beverages", "description": "Another local beer option"},
        {"name": "Agua Fresca", "price": 1200, "category": "Beverages", "description": "Fresh fruit water (tamarind, hibiscus, or lime)"},
        {"name": "Café Chorreado", "price": 1500, "category": "Beverages", "description": "Traditional Costa Rican coffee"},
        {"name": "Horchata", "price": 2000, "category": "Beverages", "description": "Rice and cinnamon drink"},
        
        # Desserts
        {"name": "Tres Leches", "price": 2800, "category": "Desserts", "description": "Traditional three-milk cake"},
        {"name": "Flan", "price": 2200, "category": "Desserts", "description": "Caramel custard dessert"},
        {"name": "Arroz con Leche", "price": 2000, "category": "Desserts", "description": "Rice pudding with cinnamon"},
    ]
    
    for item_data in restaurant_items:
        db_item = ItemModel(**item_data)
        db.add(db_item)
    
    db.commit()
    print("Restaurant menu initialized with dummy data")

# Initialize data on startup (moved after get_db definition)

# ----------------------------
# Schemas
# ----------------------------
class Item(BaseModel):
    name: str
    qty: int = Field(..., gt=0)
    price: float = Field(..., ge=0)

class ItemCreate(BaseModel):
    name: str
    price: float = Field(..., ge=0)
    category: Optional[str] = None
    description: Optional[str] = None

class ItemOut(BaseModel):
    id: int
    name: str
    price: float
    category: Optional[str]
    description: Optional[str]
    active: str
    created_at: datetime

    class Config:
        orm_mode = True

class OrderCreate(BaseModel):
    table: Optional[str] = None
    items: List[Item]

class OrderOut(BaseModel):
    id: int
    created_at: datetime
    table: Optional[str]
    items: List[Item]
    subtotal: float
    tip: float
    total: float
    status: Literal["OPEN","PAID","VOID"]

    class Config:
        orm_mode = True

class ChargeRequest(BaseModel):
    order_id: int
    tip: float = Field(0, ge=0)

class ChargeResponse(BaseModel):
    order_id: int
    amount: float
    status: Literal["approved","declined"]
    auth_code: Optional[str]
    masked_card: Optional[str]
    terminal_ref: Optional[str]

class EODReport(BaseModel):
    business_date: date
    totals_crc: dict
    transactions: List[ChargeResponse]

# ----------------------------
# DB dependency
# ----------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize data on startup
init_restaurant_data()

# ----------------------------
# Helpers
# ----------------------------

def calc_subtotal(items: List[Item]) -> float:
    return float(sum(i.qty * i.price for i in items))

# ----------------------------
# Items
# ----------------------------
@app.get("/items", response_model=List[ItemOut])
def get_items():
    db: Session = next(get_db())
    items = db.query(ItemModel).filter(ItemModel.active == "true").all()
    return items

@app.post("/items", response_model=ItemOut)
def create_item(item: ItemCreate):
    db: Session = next(get_db())
    db_item = ItemModel(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

# ----------------------------
# Orders
# ----------------------------
@app.post("/orders", response_model=OrderOut)
def create_order(payload: OrderCreate):
    db: Session = next(get_db())
    subtotal = calc_subtotal(payload.items)
    o = OrderModel(
        table=payload.table,
        items=[i.dict() for i in payload.items],
        subtotal=subtotal,
        tip=0.0,
        total=subtotal,
        status="OPEN",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o

@app.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int):
    db: Session = next(get_db())
    o = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    return o

# ----------------------------
# Payments
# ----------------------------
@app.post("/payments/charge", response_model=ChargeResponse)
def charge_order(payload: ChargeRequest):
    db: Session = next(get_db())
    o = db.query(OrderModel).filter(OrderModel.id == payload.order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.status != "OPEN":
        raise HTTPException(status_code=409, detail=f"Order status is {o.status}")

    # Update tip and total
    o.tip = float(payload.tip)
    o.total = float(o.subtotal + o.tip)
    db.commit()
    db.refresh(o)

    # POS sends only amount + reference to terminal (mocked here)
    terminal_resp = mock_terminal_charge(amount=o.total, invoice_id=str(o.id))

    # Persist transaction (non-sensitive only)
    txn = TxnModel(
        order_id=o.id,
        amount=o.total,
        status=terminal_resp["status"],
        auth_code=terminal_resp.get("auth_code"),
        masked_card=terminal_resp.get("masked_card"),
        terminal_ref=terminal_resp.get("terminal_ref"),
        terminal_meta=terminal_resp.get("terminal_meta"),
    )
    db.add(txn)

    if terminal_resp["status"] == "approved":
        o.status = "PAID"
    db.commit()

    return ChargeResponse(
        order_id=o.id,
        amount=o.total,
        status=txn.status,
        auth_code=txn.auth_code,
        masked_card=txn.masked_card,
        terminal_ref=txn.terminal_ref,
    )

# ----------------------------
# Reports
# ----------------------------
@app.get("/reports/eod", response_model=EODReport)
def end_of_day_report(date_str: Optional[str] = "today"):
    db: Session = next(get_db())

    if date_str == "today" or date_str is None:
        the_date = date.today()
    else:
        try:
            the_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Use YYYY-MM-DD or 'today'")

    start_dt = datetime(the_date.year, the_date.month, the_date.day, 0, 0, 0)
    end_dt = datetime(the_date.year, the_date.month, the_date.day, 23, 59, 59)

    q = (
        db.query(TxnModel)
        .filter(TxnModel.created_at >= start_dt)
        .filter(TxnModel.created_at <= end_dt)
    )

    txns = q.all()

    totals = {"approved": 0.0, "declined": 0.0}
    out_txns: List[ChargeResponse] = []

    for t in txns:
        totals[t.status] = round(totals.get(t.status, 0.0) + t.amount, 2)
        out_txns.append(
            ChargeResponse(
                order_id=t.order_id,
                amount=t.amount,
                status=t.status, 
                auth_code=t.auth_code,
                masked_card=t.masked_card,
                terminal_ref=t.terminal_ref,
            )
        )

    return EODReport(
        business_date=the_date,
        totals_crc={k: round(v, 2) for k, v in totals.items()},
        transactions=out_txns,
    )

# ----------------------------
# Mock Terminal (simulating BAC terminal behavior)
# ----------------------------

def mock_terminal_charge(*, amount: float, invoice_id: str) -> dict:
    if amount <= 0:
        return {
            "status": "declined",
            "terminal_ref": f"T-{invoice_id}-{int(datetime.utcnow().timestamp())}",
            "terminal_meta": {"reason": "invalid_amount"},
        }
    approved = random() < 0.90
    if approved:
        last4 = choice(["1111","4242","7777","9003"])  # demo values only
        return {
            "status": "approved",
            "auth_code": f"A{int(random()*1_000_000):06d}",
            "masked_card": f"**** **** **** {last4}",
            "terminal_ref": f"T-{invoice_id}-{int(datetime.utcnow().timestamp())}",
            "terminal_meta": {"aid": "A0000000031010", "method": choice(["chip","contactless","swipe"])},
        }
    else:
        return {
            "status": "declined",
            "terminal_ref": f"T-{invoice_id}-{int(datetime.utcnow().timestamp())}",
            "terminal_meta": {"reason": choice(["insufficient_funds","do_not_honor","expired_card"])},
        }

# ----------------------------
# Receipt (optional)
# ----------------------------
@app.get("/orders/{order_id}/receipt")
def get_receipt(order_id: int):
    db: Session = next(get_db())
    o = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    last_txn = (
        db.query(TxnModel)
        .filter(TxnModel.order_id == order_id)
        .order_by(TxnModel.created_at.desc())
        .first()
    )
    if not last_txn:
        raise HTTPException(status_code=404, detail="No transactions for this order")

    return {
        "merchant": {"name": "Demo Restaurante", "address": "San José, Costa Rica"},
        "order": {
            "id": o.id,
            "date": o.created_at.isoformat(),
            "items": o.items,
            "subtotal": round(o.subtotal, 2),
            "tip": round(o.tip, 2),
            "total": round(o.total, 2),
        },
        "payment": {
            "status": last_txn.status,
            "auth_code": last_txn.auth_code,
            "masked_card": last_txn.masked_card,
            "terminal_ref": last_txn.terminal_ref,
        },
    }
