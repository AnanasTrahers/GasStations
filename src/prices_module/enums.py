from enum import Enum


class FuelTypeEnum(str, Enum):
    A98 = "A98"
    A95_PLUS = "A95_PLUS"
    A95 = "A95"
    A92 = "A92"
    A80 = "A80"
    DIESEL = "DIESEL"
    DIESEL_PLUS = "DIESEL_PLUS"
    LPG = "LPG"


class RegionEnum(str, Enum):
    KYIV = "KYIV"