from src.scrapers.enums import FuelTypeEnum, RegionEnum


class VseazsMapper:
    """Maps app-level enums to VseAZS API request-specific values."""
    _FUEL_TO_ID: dict[FuelTypeEnum, int] = {
        FuelTypeEnum.A98: 1,
        FuelTypeEnum.A95_PLUS: 2,
        FuelTypeEnum.A95: 3,
        FuelTypeEnum.A92: 4,
        FuelTypeEnum.A80: 5,
        FuelTypeEnum.DIESEL: 6,
        FuelTypeEnum.DIESEL_PLUS: 7,
        FuelTypeEnum.LPG: 8,
    }

    _REGION_TO_ID: dict[RegionEnum, int] = {
        RegionEnum.KYIV: 9,
    }

    @classmethod
    def get_fuel(cls, fuel: FuelTypeEnum) -> int:
        """Return VseAZS PriceID (1-8) for the given FuelTypeEnum member."""
        return cls._FUEL_TO_ID[fuel]

    @classmethod
    def get_region(cls, region: RegionEnum) -> int:
        """Return VseAZS ID_region for the given RegionEnum member."""
        return cls._REGION_TO_ID[region]
