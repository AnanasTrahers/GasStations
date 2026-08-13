import httpx

from src.prices_module.network_registry import normalize_network_name, is_known_network
from src.prices_module.schemas import StationRecord
from src.prices_module.scrapers.base import BaseScraper
from src.prices_module.settings import scraper_settings

# Ukraine bounding box: south, west, north, east
_UA_BBOX = "44.3,22.1,52.4,40.2"

_OVERPASS_QUERY = (
    '[out:json][timeout:180];'
    f'(nwr["amenity"="fuel"]({_UA_BBOX}););'
    'out center;'
)


class OverpassScraper(BaseScraper):
    SOURCE = "overpass"
    BASE_URL = "https://overpass.openstreetmap.fr/api/interpreter"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client=client)

    async def collect(self) -> list[StationRecord]:
        """Fetch all fuel stations in Ukraine and return normalised records.
        Stations whose network name doesn't match any registry entry are
        filtered out.
        """
        self.log_info("Querying Overpass API for Ukrainian fuel stations")
        raw = await self._post(
            url=self.BASE_URL,
            data={"data": _OVERPASS_QUERY},
            timeout=scraper_settings.OVERPASS_TIMEOUT,
            headers={"User-Agent": "GasStationsApp/1.0"},
        )
        elements = raw.json().get("elements", [])
        self.log_info(f"Received {len(elements)} OSM elements")

        records: list[StationRecord] = []
        skipped_no_name = 0
        skipped_no_coords = 0
        skipped_unmatched: set[str] = set()

        for el in elements:
            tags = el.get("tags", {})

            # Extract coordinates — nodes have lat/lon directly,
            # ways have a 'center' dict from `out center`.
            if el["type"] == "node":
                lat = el.get("lat")
                lng = el.get("lon")
            else:
                center = el.get("center", {})
                lat = center.get("lat")
                lng = center.get("lon")

            if lat is None or lng is None:
                skipped_no_coords += 1
                continue

            # Extract network name: brand > operator > name > name:uk
            raw_name = (
                    tags.get("brand")
                    or tags.get("operator")
                    or tags.get("name")
                    or tags.get("name:uk")
            )
            if not raw_name:
                skipped_no_name += 1
                continue

            if not is_known_network(raw_name):
                skipped_unmatched.add(raw_name)
                continue

            canonical = normalize_network_name(raw_name)
            records.append(
                StationRecord(
                    network_name=canonical,
                    lat=lat,
                    lng=lng,
                    osm_id=el["id"],
                )
            )

        self.log_info(
            f"Produced {len(records)} station records "
            f"across {len({r.network_name for r in records})} networks",
            skipped_no_name=skipped_no_name,
            skipped_no_coords=skipped_no_coords,
            skipped_unmatched=len(skipped_unmatched),
        )
        if skipped_unmatched:
            self.log_info(
                "Sample unrecognised brands (not in registry)",
                sample=sorted(skipped_unmatched)[:20],
            )
        return records
