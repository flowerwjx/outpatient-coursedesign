from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)

from app.database import Base


class Drug(Base):
    __tablename__ = "drugs"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_drugs_unit_price_non_negative"),
        CheckConstraint("stock >= 0", name="ck_drugs_stock_non_negative"),
        UniqueConstraint(
            "generic_name",
            "trade_name",
            "spec",
            "dosage_form",
            name="uq_drugs_generic_trade_spec_form",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    generic_name = Column(String(100), nullable=False, index=True)
    trade_name = Column(String(100), nullable=False, default="")
    spec = Column(String(100), nullable=False)
    dosage_form = Column(String(50), nullable=False)
    insurance_type = Column(String(50), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Drug id={self.id} generic_name={self.generic_name!r} "
            f"spec={self.spec!r} unit_price={self.unit_price} stock={self.stock}>"
        )
