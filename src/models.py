import uuid
from datetime import datetime

from geoalchemy2 import Geography, WKBElement, WKTElement
from sqlalchemy import JSON as SAJSON
from sqlalchemy import String, func, ForeignKey, DateTime, Float, Index, Boolean
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


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    google_id: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)

    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        back_populates="user",
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    purchase_token: Mapped[str | None] = mapped_column(
        String(1024), unique=True, nullable=True
    )
    product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    user: Mapped[User] = relationship("User", back_populates="subscription")


class SubscriptionHistory(Base):
    __tablename__ = "subscription_history"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    purchase_token: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
