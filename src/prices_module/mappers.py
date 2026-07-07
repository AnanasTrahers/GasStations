import re
import string

from src.prices_module.enums import FuelTypeEnum, RegionEnum


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


class MinfinMapper:
    """Maps app-level enums to minfin-specific values and parses minfin HTML labels."""

    _FUEL_TO_LABEL: dict[FuelTypeEnum, str] = {
        FuelTypeEnum.A95_PLUS: "а-95 преміум",
        FuelTypeEnum.A95: "а-95",
        FuelTypeEnum.A92: "а-92",
        FuelTypeEnum.DIESEL: "дизельне паливо",
        FuelTypeEnum.LPG: "газ автомобільний",
    }

    # Order matters: more specific patterns first.
    _LABEL_PATTERNS: list[tuple[str, FuelTypeEnum]] = [
        ("а-95 преміум", FuelTypeEnum.A95_PLUS),
        ("а 95 преміум", FuelTypeEnum.A95_PLUS),
        ("а 95+", FuelTypeEnum.A95_PLUS),
        ("а-95+", FuelTypeEnum.A95_PLUS),
        ("а 95", FuelTypeEnum.A95),
        ("а-95", FuelTypeEnum.A95),
        ("а 92", FuelTypeEnum.A92),
        ("а-92", FuelTypeEnum.A92),
        ("дизельне паливо", FuelTypeEnum.DIESEL),
        ("дизель", FuelTypeEnum.DIESEL),
        ("дп", FuelTypeEnum.DIESEL),
        ("газ автомобільний", FuelTypeEnum.LPG),
        ("газ", FuelTypeEnum.LPG),
    ]

    @classmethod
    def get_fuel_label(cls, fuel: FuelTypeEnum) -> str:
        """Return the primary Ukrainian label for a FuelTypeEnum member."""
        return cls._FUEL_TO_LABEL[fuel]

    @classmethod
    def parse_fuel_label(cls, label: str) -> FuelTypeEnum | None:
        """Parse a Ukrainian fuel label from minfin HTML into a FuelTypeEnum member."""
        key = re.sub(fr"[{string.whitespace}\xa0]", " ", label.lower().strip())
        key = re.sub(r"\s{2,}", " ", key)
        for pattern, fuel_type in cls._LABEL_PATTERNS:
            if pattern in key:
                return fuel_type
        return None
