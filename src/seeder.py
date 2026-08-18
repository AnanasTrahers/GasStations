import asyncio
import uuid
from uuid import UUID
from datetime import date
from decimal import Decimal

from geoalchemy2 import WKTElement
from sqlalchemy import select

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
        # mn1 = UUID("10fb5c13-a7ba-4fd1-a27e-d9dc1839a9a8")
        # mn2 = UUID("f7971df0-dc34-4697-b7ed-cbf89644eb92")
        # mn3 = UUID("5a761bdc-9996-4a76-8f7a-8c217bfe8bac")
        # mn4 = UUID("6e5346a5-ec1b-4015-910b-8484b149203b")
        #
        # # Create Fuel Prices for the networks
        # session.add_all([
        #     FuelPrice(network_id=mn1, fuel_type=FuelTypeEnum.A95, price=54.50),
        #     FuelPrice(network_id=mn1, fuel_type=FuelTypeEnum.DIESEL, price=50.20),
        #     FuelPrice(network_id=mn1, fuel_type=FuelTypeEnum.LPG, price=28.40),
        #
        #     FuelPrice(network_id=mn2, fuel_type=FuelTypeEnum.A95, price=56.99),
        #     FuelPrice(network_id=mn2, fuel_type=FuelTypeEnum.DIESEL, price=52.99),
        #     FuelPrice(network_id=mn2, fuel_type=FuelTypeEnum.LPG, price=29.99),
        #
        #     FuelPrice(network_id=mn3, fuel_type=FuelTypeEnum.A95, price=57.99),
        #     FuelPrice(network_id=mn3, fuel_type=FuelTypeEnum.DIESEL, price=53.99),
        #     FuelPrice(network_id=mn3, fuel_type=FuelTypeEnum.LPG, price=29.49),
        #
        #     FuelPrice(network_id=mn4, fuel_type=FuelTypeEnum.A95, price=53.40),
        #     FuelPrice(network_id=mn4, fuel_type=FuelTypeEnum.DIESEL, price=49.90),
        #     FuelPrice(network_id=mn4, fuel_type=FuelTypeEnum.LPG, price=27.90),
        # ])

        # Query existing networks that should have been populated by the price ETL
        stmt = select(Network).where(Network.name.in_(["WOG", "ОККО", "UPG", "SOCAR"]))
        networks = (await session.execute(stmt)).scalars().all()
        
        network_map = {n.name: n.id for n in networks}
        
        if not network_map:
            print(
                "No networks found! Run the price ETL first to populate Networks and Prices:\n"
                "  uv run python -m src.worker.trigger fuel_prices_etl --now"
            )
            return

        stations = []
        
        # Helper to safely create a station if the network exists
        def add_station(net_name, wkt_point):
            if net_name in network_map:
                stations.append(GasStation(network_id=network_map[net_name], geog=WKTElement(wkt_point, srid=4326)))

        add_station("WOG", "POINT(30.5234 50.4501)")   # Maidan Nezalezhnosti
        add_station("ОККО", "POINT(30.5140 50.4635)")  # Kontraktova Ploshcha
        add_station("UPG", "POINT(30.5363 50.4430)")   # Pechersk
        add_station("SOCAR", "POINT(30.4900 50.4480)") # Vokzalna (Railway station)
        add_station("ОККО", "POINT(30.5145 50.4640)")  # Kontraktova Ploshcha 2
        
        if stations:
            session.add_all(stations)
            await session.commit()
            print(f"Database seeded successfully with {len(stations)} stations in Kyiv.")
        else:
            print("No matching networks found to seed stations.")

if __name__ == "__main__":
    asyncio.run(seed_db())
