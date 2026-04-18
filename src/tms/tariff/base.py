from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal, Optional


@dataclass
class TariffResult:
    basispreis: Decimal
    diesel_surcharge: Decimal | None
    maut_surcharge: Decimal | None
    other_surcharges: dict[str, Decimal] = field(default_factory=dict)
    currency: str = "EUR"
    tariff_file: str = ""
    tariff_valid_from: date = date(1970, 1, 1)
    tariff_valid_to: date | None = None
    notes: list[str] = field(default_factory=list)
    # ── Etappe 6e: Tarif-Tracking ─────────────────────────────────────────
    tarifgruppe: str = ""              # stabiler Cluster-Key pro Tarif-Segment
    tariff_file_used: str = ""         # Dateiname der tatsächlich verwendeten DLV
    tariff_year_used: int = 0          # tatsächlich verwendetes DLV-Jahr
    tariff_fallback_note: Optional[str] = None  # gesetzt wenn Fallback auf älteres Jahr

    @property
    def total(self) -> Decimal:
        total = self.basispreis
        if self.diesel_surcharge is not None:
            total += self.diesel_surcharge
        if self.maut_surcharge is not None:
            total += self.maut_surcharge
        for v in self.other_surcharges.values():
            total += v
        return total


class TariffCalculator(ABC):
    customer_name: str
    pricing_basis: Literal["kg", "stellplaetze", "lademeter"]

    @abstractmethod
    def calculate(
        self,
        empf_plz: str,
        empf_land: str,
        *,
        lademeter: float | None = None,
        stellplaetze: int | None = None,
        tonnage_kg: float | None = None,
        ldm: float | None = None,
    ) -> TariffResult:
        """Return TariffResult for a shipment. Raises LookupError if no rate found."""
        ...
