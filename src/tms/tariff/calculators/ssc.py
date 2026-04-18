"""
SIKA Supply Center AG (KNR 511241) tariff calculator.

Uses the same Sika DE & SSC DLV as SikaDeCalculator — see sika_de.py.
"""
from tms.tariff.calculators.sika_de import SSCCalculator

__all__ = ["SSCCalculator"]
