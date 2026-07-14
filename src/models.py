import uuid
from datetime import datetime

from geoalchemy2 import Geography, WKBElement, WKTElement
from sqlalchemy import String, func, ForeignKey, DateTime, Float, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, relationship, mapped_column

from src.database import Base


class Network(Base):
    __tablename__ = "networks"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
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

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    geog: Mapped[str | WKBElement | WKTElement] = mapped_column(
        Geography(geometry_type="Point", srid=4326)
    )
    network_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("networks.id"))

    network: Mapped[Network] = relationship(
        "Network",
        back_populates="stations",
    )


class FuelPrice(Base):
    __tablename__ = "fuel_prices"
    __table_args__ = (
        Index("ix_fuel_prices_created_at_fuel_type", "created_at", "fuel_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    price: Mapped[float] = mapped_column(Float)
    fuel_type: Mapped[str] = mapped_column(String(32))
    network_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("networks.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    network: Mapped[Network] = relationship(
        "Network",
        back_populates="prices",
    )
