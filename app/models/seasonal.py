from sqlalchemy import CHAR, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SeasonalProduce(Base):
    """Months in which a vegetable or fruit is in season in a region (spec v0.2.0 §3.3).

    Reference data loaded by migration; the menu generator uses it to prefer
    seasonal recipes (GEN-6). ``name`` is normalised (GEN-1).
    """

    __tablename__ = "seasonal_produce"
    __table_args__ = (UniqueConstraint("region", "name", name="uq_seasonal_produce_region_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    months: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)
