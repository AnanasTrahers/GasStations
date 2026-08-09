import asyncio
import uuid
from uuid import UUID
from datetime import date
from decimal import Decimal

from geoalchemy2 import WKTElement

from src.database import AsyncSessionLocal, engine
from src.models import Base, Network, GasStation, FuelPrice
from src.prices_module.enums import FuelTypeEnum, RegionEnum

async def seed_db():
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.drop_all)
    #     await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Create Networks
        # network1 = Network(id=uuid.uuid4(), name="Kyiv Oil")
        # network2 = Network(id=uuid.uuid4(), name="WOG")
        # network3 = Network(id=uuid.uuid4(), name="OKKO")
        # network4 = Network(id=uuid.uuid4(), name="UPG")
        # session.add_all([network1, network2, network3, network4])
        #
        # # Create Fuel Prices for the networks
        # session.add_all([
        #     FuelPrice(network_id=network1.id, fuel_type="A-95", price=54.50),
        #     FuelPrice(network_id=network1.id, fuel_type="Diesel", price=50.20),
        #     FuelPrice(network_id=network1.id, fuel_type="Gas", price=28.40),
        #
        #     FuelPrice(network_id=network2.id, fuel_type="A-95", price=56.99),
        #     FuelPrice(network_id=network2.id, fuel_type="Diesel", price=52.99),
        #     FuelPrice(network_id=network2.id, fuel_type="Gas", price=29.99),
        #
        #     FuelPrice(network_id=network3.id, fuel_type="A-95", price=57.99),
        #     FuelPrice(network_id=network3.id, fuel_type="Diesel", price=53.99),
        #     FuelPrice(network_id=network3.id, fuel_type="Gas", price=29.49),
        #
        #     FuelPrice(network_id=network4.id, fuel_type="A-95", price=53.40),
        #     FuelPrice(network_id=network4.id, fuel_type="Diesel", price=49.90),
        #     FuelPrice(network_id=network4.id, fuel_type="Gas", price=27.90),
        # ])

        mn1 = UUID("10fb5c13-a7ba-4fd1-a27e-d9dc1839a9a8")
        mn2 = UUID("f7971df0-dc34-4697-b7ed-cbf89644eb92")
        mn3 = UUID("5a761bdc-9996-4a76-8f7a-8c217bfe8bac")
        mn4 = UUID("6e5346a5-ec1b-4015-910b-8484b149203b")

        # Create Gas Stations in Kyiv assigned to different networks
        stations = [
            GasStation(
                network_id=mn1,
                geog=WKTElement("POINT(30.5234 50.4501)", srid=4326) # Maidan Nezalezhnosti
            ),
            GasStation(
                network_id=mn2,
                geog=WKTElement("POINT(30.5140 50.4635)", srid=4326) # Kontraktova Ploshcha
            ),
            GasStation(
                network_id=mn3,
                geog=WKTElement("POINT(30.5363 50.4430)", srid=4326) # Pechersk
            ),
            GasStation(
                network_id=mn4,
                geog=WKTElement("POINT(30.4900 50.4480)", srid=4326) # Vokzalna (Railway station)
            ),
            GasStation(
                network_id=mn3,
                geog=WKTElement("POINT(30.5145 50.4640)", srid=4326)  # Kontraktova Ploshcha
            ),
        ]
        session.add_all(stations)
        
        await session.commit()
        print("Database seeded successfully with 5 stations in Kyiv.")

if __name__ == "__main__":
    asyncio.run(seed_db())
