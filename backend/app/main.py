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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
# Schemas
# ----------------------------
class Item(BaseModel):
    name: str
    qty: int = Field(..., gt=0)
    price: float = Field(..., ge=0)

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

# ----------------------------
# Helpers
# ----------------------------

def calc_subtotal(items: List[Item]) -> float:
    return float(sum(i.qty * i.price for i in items))

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
