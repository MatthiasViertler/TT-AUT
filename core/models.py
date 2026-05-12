"""
Core data models.
All broker parsers convert their raw data into these normalized types.
This is the lingua franca of the entire pipeline.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional
from enum import Enum


class TransactionType(str, Enum):
    DIVIDEND       = "dividend"
    DIVIDEND_WHT   = "dividend_wht"   # Withholding tax deducted (negative amount)
    BUY            = "buy"
    SELL           = "sell"
    INTEREST       = "interest"
    CORPORATE_ACT  = "corporate_action"
    FX_GAIN_LOSS   = "fx_gain_loss"
    DEPOSIT        = "deposit"
    WITHDRAWAL     = "withdrawal"
    CASH_TRANSFER  = "cash_transfer"
    FX_TRANSFER    = "fx_transfer"
    UNKNOWN        = "unknown"


class AssetClass(str, Enum):
    STOCK   = "stock"
    ETF     = "etf"
    BOND    = "bond"
    FUND    = "fund"
    OPTION  = "option"
    CASH    = "cash"
    OTHER   = "other"


class Domicile(str, Enum):
    DOMESTIC  = "domestic"   # Austrian security (ISIN starts AT, or listed on Vienna SE)
    FOREIGN   = "foreign"
    UNKNOWN   = "unknown"


@dataclass
class NormalizedTransaction:
    """
    One broker event in a fully normalized, broker-agnostic representation.
    All monetary amounts are in the ORIGINAL currency (orig_currency).
    EUR equivalents (eur_amount etc.) are filled in by the FX enrichment step.
    """
    # Identity
    broker:           str               # "ib", "degiro", "flatex", …
    raw_id:           str               # Original broker transaction ID (for dedup)

    # Timing
    trade_date:       date
    settle_date:      Optional[date]

    # What
    txn_type:         TransactionType
    asset_class:      AssetClass

    # Instrument
    symbol:           str
    isin:             Optional[str]
    description:      str
    country_code:     Optional[str]     # ISO 3166-1 alpha-2, e.g. "US", "DE"
    domicile:         Domicile          # domestic (AT) vs foreign

    # Position (for buys/sells)
    quantity:         Optional[Decimal]
    price:            Optional[Decimal]
    price_currency:   Optional[str]

    # Money
    orig_currency:    str               # Currency of the transaction as booked
    orig_amount:      Decimal           # Signed: positive = cash in, negative = cash out

    # Costs
    commission:       Decimal = Decimal(0)
    commission_currency: Optional[str] = None

    # Withholding tax (populated from broker data OR matched from dividend_wht rows)
    wht_rate_actual:  Optional[Decimal] = None   # Rate actually applied by source country
    wht_amount_orig:  Decimal = Decimal(0)       # Amount in orig_currency (positive)

    # FX enrichment (filled by fx module)
    fx_rate_to_eur:   Optional[Decimal] = None   # 1 orig_currency = N EUR on trade_date
    eur_amount:       Optional[Decimal] = None
    eur_commission:   Optional[Decimal] = None
    eur_wht:          Optional[Decimal] = None

    # Tax computed fields (filled by tax engine)
    eur_gain_loss:    Optional[Decimal] = None   # For sells: proceeds - cost basis
    eur_cost_basis:   Optional[Decimal] = None   # For sells: matched purchase cost

    # Broker-reported FIFO PnL (EUR) — used for cross-check against our computation
    broker_fifo_pnl_eur: Optional[Decimal] = None

    # Metadata
    source_file:      str = ""
    notes:            str = ""


@dataclass
class NichtmeldefondsResult:
    """
    Per-position Nichtmeldefonds (unregistered fund) result for one tax year.
    Tax base: pauschal AE = max(90% × annual gain, 10% × Dec31 price) per share.
    """
    symbol:       str
    isin:         str
    name:         str
    fund_type:    str            # "REIT", "BDC", "FUND"
    currency:     str

    shares_held:  Decimal        # at Dec 31 of tax year

    price_jan1:   Optional[Decimal]   # Jan 1 (= prior Dec 31) in native currency
    price_dec31:  Optional[Decimal]   # Dec 31 in native currency
    fx_dec31:     Optional[Decimal]   # EUR/native on Dec 31

    annual_gain_per_share:  Decimal = Decimal(0)
    ae_90pct_per_share:     Decimal = Decimal(0)   # 90% × gain
    ae_10pct_per_share:     Decimal = Decimal(0)   # 10% × dec31 price (minimum)
    ae_per_share:           Decimal = Decimal(0)   # max of above two

    ae_total_native:        Decimal = Decimal(0)
    ae_total_eur:           Decimal = Decimal(0)
    kest_due_eur:           Decimal = Decimal(0)
    cost_basis_adj_eur:     Decimal = Decimal(0)   # = ae_total_eur (prevents double-tax on sale)

    warning: str = ""


@dataclass
class MatchedTrade:
    """
    A realized gain/loss: one SELL matched against one or more BUYs.
    Austrian tax uses FIFO by default.
    """
    sell_txn:         NormalizedTransaction
    buy_txns:         list[NormalizedTransaction] = field(default_factory=list)

    eur_proceeds:     Decimal = Decimal(0)
    eur_cost:         Decimal = Decimal(0)
    eur_gain_loss:    Decimal = Decimal(0)    # positive = gain, negative = loss

    domicile:         Domicile = Domicile.UNKNOWN


@dataclass
class TaxSummary:
    """
    The final aggregated output — maps directly to E1kv Kennziffern.
    All amounts in EUR.
    """
    tax_year:         int
    person_label:     str

    # ── E1kv Kennziffern — Section 1.3.1 (Dividenden, Zinsen §27 Abs. 2) ───────
    kz_862: Decimal = Decimal(0)   # Inländische Dividenden + Zinserträge
    kz_863: Decimal = Decimal(0)   # Ausländische Dividenden + Zinserträge

    # ── Section 1.3.2 (Kursgewinne §27 Abs. 3) ───────────────────────────────
    kz_981: Decimal = Decimal(0)   # Inländische Kursgewinne 27.5%
    kz_994: Decimal = Decimal(0)   # Ausländische Kursgewinne 27.5%
    kz_864: Decimal = Decimal(0)   # Inländische Kursgewinne 25% (pre-2011 securities)
    kz_865: Decimal = Decimal(0)   # Ausländische Kursgewinne 25%
    kz_891: Decimal = Decimal(0)   # Inländische Kursverluste (positive value)
    kz_892: Decimal = Decimal(0)   # Ausländische Kursverluste (positive value)

    # ── Section 1.3.3 (Derivate §27 Abs. 4) ──────────────────────────────────
    kz_982: Decimal = Decimal(0)   # Inländische Derivate-Gewinne 27.5%
    kz_993: Decimal = Decimal(0)   # Ausländische Derivate-Gewinne 27.5%
    kz_893: Decimal = Decimal(0)   # Inländische Derivate-Gewinne 25%
    kz_894: Decimal = Decimal(0)   # Ausländische Derivate-Gewinne 25%
    kz_895: Decimal = Decimal(0)   # Inländische Derivate-Verluste
    kz_896: Decimal = Decimal(0)   # Ausländische Derivate-Verluste

    # ── Section 1.3.4 (Investmentfonds) ──────────────────────────────────────
    kz_897: Decimal = Decimal(0)   # Inländische Fonds-Ausschüttungen 27.5%
    kz_898: Decimal = Decimal(0)   # Ausländische Fonds-Ausschüttungen 27.5%
    kz_936: Decimal = Decimal(0)   # Inländische Ausschüttungsgleiche Erträge
    kz_937: Decimal = Decimal(0)   # Ausländische Ausschüttungsgleiche Erträge (requires OeKB)

    # ── Section 1.3.5 (Kryptowährungen §27b) ─────────────────────────────────
    kz_171: Decimal = Decimal(0)   # Krypto Laufende Einkünfte
    kz_173: Decimal = Decimal(0)   # Krypto Kursgewinne
    kz_175: Decimal = Decimal(0)   # Krypto Verluste

    # ── Saldo aus Punkt 1.3 ───────────────────────────────────────────────────
    saldo_inland:  Decimal = Decimal(0)   # Net domestic capital income
    saldo_ausland: Decimal = Decimal(0)   # Net foreign capital income

    # ── Section 1.4 (KESt bereits bezahlt) ───────────────────────────────────
    kz_899: Decimal = Decimal(0)   # KESt für inländ. WP im Ausland bereits bezahlt

    # ── Section 1.5 (Abgeltungssteuer) ───────────────────────────────────────
    kz_942: Decimal = Decimal(0)   # Abgeltungssteuer Liechtenstein (N/A for most)

    # ── Section 1.6 (Anzurechnende QSt 27.5%) ────────────────────────────────
    kz_984: Decimal = Decimal(0)   # Anrechenbare QSt auf inländ. Einkünfte 27.5%
    kz_998: Decimal = Decimal(0)   # Anrechenbare QSt auf ausländ. Einkünfte 27.5%

    # ── Section 1.7 (Anzurechnende QSt 25%) ──────────────────────────────────
    kz_900: Decimal = Decimal(0)   # Anrechenbare QSt auf inländ. Einkünfte 25%
    kz_901: Decimal = Decimal(0)   # Anrechenbare QSt auf ausländ. Einkünfte 25%

    # ── Derived / informational ───────────────────────────────────────────────
    total_dividends_eur:    Decimal = Decimal(0)
    total_gains_eur:        Decimal = Decimal(0)
    total_losses_eur:       Decimal = Decimal(0)
    total_wht_paid_eur:     Decimal = Decimal(0)
    net_taxable_eur:        Decimal = Decimal(0)

    kest_due_eur:           Decimal = Decimal(0)   # 27.5% on net_taxable
    wht_creditable_eur:     Decimal = Decimal(0)   # Min(wht_paid, treaty_max * gross)
    kest_remaining_eur:     Decimal = Decimal(0)   # kest_due - wht_creditable

    # ── Nichtmeldefonds ───────────────────────────────────────────────────────
    nichtmeldefonds:            list = field(default_factory=list)  # list[NichtmeldefondsResult]
    nichtmeldefonds_ae_eur:     Decimal = Decimal(0)
    nichtmeldefonds_kest_eur:   Decimal = Decimal(0)

    # ── Portfolio snapshot (computed from remaining FIFO lots at Dec 31) ─────
    # Populated by the pipeline after tax calculation. None = not computed.
    # Sourced from: transaction FIFO remainder × Dec31 market price × ECB FX.
    # Future: can also be seeded from broker portfolio reports (position exports).
    portfolio_eur_computed: Optional[Decimal] = None

    # ── Diagnostics ──────────────────────────────────────────────────────────
    transaction_count:      int = 0
    unmatched_sells:        int = 0    # Sells with no matching buy (warn user)
    missing_fx_count:       int = 0    # Transactions where FX rate was unavailable
    warnings:               list[str] = field(default_factory=list)
