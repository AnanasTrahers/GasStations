from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy import String, func, ForeignKey, Numeric, DateTime
from geoalchemy2 import Geography, WKBElement

from src.database import Base


class Network(Base):
    __tablename__ = "networks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)

    stations: Mapped[list["GasStation"]] = relationship(
        "GasStation",
        back_populates="network"
    )
    prices: Mapped[list["FuelPrice"]] = relationship(
        "FuelPrice",
        back_populates="network"
    )


class GasStation(Base):
    __tablename__ = "gas_stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    geog: Mapped[str | WKBElement] = mapped_column(
        Geography(geometry_type="Point", srid=4326)
    )
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"))

    network: Mapped[Network] = relationship(
        "Network",
        back_populates="stations",
    )


class FuelPrice(Base):
    __tablename__ = "fuel_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    fuel_type: Mapped[str] = mapped_column(String(32))
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    network: Mapped[Network] = relationship(
        "Network",
        back_populates="prices",
    )
