from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal, NamedTuple, Optional


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
    billing_scope: str = "position"

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


class RNPosition(NamedTuple):
    """Input record for RN-level (billing_scope='rn') calculators.

    All positions of one invoice (RN) are passed together so that
    HL/Maut can be computed on total RN weight and NL per Empfänger-Gruppe.
    """
    position_id: int | str
    empf_plz: str
    empf_land: str
    empfaenger_name: str
    actual_kg: float


class RNLevelCalculator(ABC):
    """Base for calculators where HL/Maut are shared across an entire RN
    and NL is computed per Empfänger-Gruppe (RN, Empfänger_Name).

    billing_scope = "rn"
    """

    customer_name: str
    pricing_basis: str = "kg"
    billing_scope: str = "rn"

    @abstractmethod
    def calc_rn(
        self,
        positions: list[RNPosition],
    ) -> dict[int | str, TariffResult]:
        """Compute prorated TariffResult per position_id for all positions in one RN.

        Raises LookupError if zone/rate cannot be determined.
        Raises ValueError if positions list is empty or has invalid data.
        """
        ...
