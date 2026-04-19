"""
Backfill insider trades from SEC EDGAR Form 4 filings (2004-present).

Uses the SEC EDGAR submissions API + Form 4 XML to extract open-market
purchases (P) and sales (S) for the equity universe defined in
fmp_earnings_surprises.SYMBOLS (~75 names).

Writes to the same ArcticDB key as the FMP collector (macro/INSIDER_TRADES),
merging SEC historical data with existing FMP data. FMP data wins for overlap.

Runtime estimate: ~75 symbols × ~200 filings each × 0.12s = ~30 minutes.
Older filings use .txt format (pre-2004 XML) and are skipped automatically.

Usage:
    python util/ingest_sec_insider.py
    python util/ingest_sec_insider.py --start 2010-01-01   # partial backfill
"""

import argparse
import logging
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.collectors.fmp_earnings_surprises import SYMBOLS
from data.store import get_store

log = logging.getLogger(__name__)

BASE_URL = "https://data.sec.gov"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ARC_LIB = "macro"
ARC_KEY = "INSIDER_TRADES"
REQUEST_SLEEP = 0.12
HEADERS = {"User-Agent": "QuantWorkstation/1.0 burkswill2@gmail.com"}

# Only keep open-market buys and sells — skip exercises (M), vests (F/G/V/R), gifts, etc.
KEEP_CODES = {"P", "S"}


# ---------------------------------------------------------------------------
# SEC helpers
# ---------------------------------------------------------------------------


def _get(url: str, session: requests.Session, retries: int = 4) -> requests.Response:
    for attempt in range(retries):
        try:
            resp = session.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 429:
                wait = 2**attempt
                log.warning("Rate limited — sleeping %ds", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            time.sleep(REQUEST_SLEEP)
            return resp
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"Failed to fetch {url}")


def _load_ticker_cik_map(session: requests.Session) -> dict[str, str]:
    """Return {ticker: cik_padded_10} from SEC company_tickers.json."""
    resp = _get(TICKERS_URL, session)
    data = resp.json()
    return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()}


def _get_form4_filings(cik: str, session: requests.Session, start_date: datetime) -> list[dict[str, Any]]:
    """Return list of {accession, filing_date, primary_doc} for all Form 4s since start_date."""
    results: list[dict[str, Any]] = []
    url = f"{BASE_URL}/submissions/CIK{cik}.json"
    resp = _get(url, session)
    data = resp.json()

    def _extract_filings(filings_block: dict[str, Any]) -> None:
        forms = filings_block.get("form", [])
        dates = filings_block.get("filingDate", [])
        accessions = filings_block.get("accessionNumber", [])
        docs = filings_block.get("primaryDocument", [])

        for form, date_str, acc, doc in zip(forms, dates, accessions, docs):
            if form not in ("4", "4/A"):
                continue
            filing_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
            if filing_date < start_date:
                continue
            # Skip old .txt format filings (pre-XML, harder to parse)
            if not doc.lower().endswith(".xml"):
                continue
            results.append(
                {
                    "accession": acc,
                    "filing_date": filing_date,
                    "primary_doc": doc,
                    "cik": cik,
                }
            )

    # Recent filings (inline)
    _extract_filings(data.get("filings", {}).get("recent", {}))

    # Older filings (paginated)
    for page_file in data.get("filings", {}).get("files", []):
        page_url = f"{BASE_URL}/submissions/{page_file['name']}"
        try:
            page_resp = _get(page_url, session)
            _extract_filings(page_resp.json())
        except Exception as exc:
            log.warning("Failed to fetch filing page %s: %s", page_file["name"], exc)

    return results


def _parse_form4_xml(xml_bytes: bytes, ticker: str, filing_date: datetime) -> list[dict[str, Any]]:
    """Parse Form 4 XML and return list of transaction dicts (P and S codes only)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        log.warning("XML parse error for %s: %s", ticker, exc)
        return []

    def _text(el: ET.Element, path: str) -> str:
        node = el.find(path)
        return node.text.strip() if node is not None and node.text else ""

    # Insider name and title
    owner_name = _text(root, "reportingOwner/reportingOwnerId/rptOwnerName")
    is_director = _text(root, "reportingOwner/reportingOwnerRelationship/isDirector")
    title = _text(root, "reportingOwner/reportingOwnerRelationship/officerTitle")
    if not title:
        title = "Director" if is_director.lower() == "true" else "Officer"

    transactions = []
    for txn in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _text(txn, "transactionCoding/transactionCode")
        if code not in KEEP_CODES:
            continue

        date_str = _text(txn, "transactionDate/value")
        try:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        except (ValueError, TypeError):
            txn_date = filing_date

        shares_str = _text(txn, "transactionAmounts/transactionShares/value")
        price_str = _text(txn, "transactionAmounts/transactionPricePerShare/value")
        a_or_d = _text(txn, "transactionAmounts/transactionAcquiredDisposedCode/value")

        try:
            shares = float(shares_str) if shares_str else None
        except ValueError:
            shares = None
        try:
            price = float(price_str) if price_str else None
        except ValueError:
            price = None

        transactions.append(
            {
                "symbol": ticker,
                "reporting_name": owner_name,
                "transaction_type": code,
                "acquisition_or_disposition": a_or_d,
                "securities_transacted": shares,
                "price": price,
                "securities_owned": None,
                "_date": txn_date,
            }
        )

    return transactions


# ---------------------------------------------------------------------------
# Main ingest
# ---------------------------------------------------------------------------


def ingest(start_date: datetime) -> None:
    session = requests.Session()

    log.info("Loading SEC ticker→CIK map…")
    ticker_cik = _load_ticker_cik_map(session)

    # Load existing data once to determine merge cutoff
    store = get_store()
    try:
        existing = store.read_series(ARC_LIB, ARC_KEY)
        existing_end = (
            existing.index.max() if not existing.empty else pd.Timestamp.min.tz_localize("UTC")
        )
        log.info("Existing INSIDER_TRADES: %d rows up to %s", len(existing), existing_end.date())
    except Exception:
        existing = pd.DataFrame()
        existing_end = pd.Timestamp.min.tz_localize("UTC")

    all_txns: list[dict[str, Any]] = []
    skipped_symbols: list[str] = []

    for idx, symbol in enumerate(SYMBOLS):
        cik = ticker_cik.get(symbol.upper())
        if not cik:
            log.warning("[%d/%d] %s: no CIK found — skipping", idx + 1, len(SYMBOLS), symbol)
            skipped_symbols.append(symbol)
            continue

        log.info("[%d/%d] %s (CIK %s)", idx + 1, len(SYMBOLS), symbol, cik)

        try:
            filings = _get_form4_filings(cik, session, start_date)
        except Exception as exc:
            log.warning("%s: failed to get filing list — %s", symbol, exc)
            continue

        log.info("  %d Form 4 XML filings since %s", len(filings), start_date.date())

        for filing in filings:
            acc_nodash = filing["accession"].replace("-", "")
            doc = filing["primary_doc"]
            # Strip XSL prefix if present (e.g. "xslF345X06/form4.xml" → "form4.xml")
            if "/" in doc:
                doc = doc.split("/")[-1]
            xml_url = f"{ARCHIVES_URL}/{int(cik)}/{acc_nodash}/{doc}"

            try:
                resp = _get(xml_url, session)
                txns = _parse_form4_xml(resp.content, symbol, filing["filing_date"])
                all_txns.extend(txns)
            except Exception as exc:
                log.warning("  %s filing %s: %s", symbol, filing["accession"], exc)
                continue

        if all_txns and idx % 10 == 0:
            log.info("  Running total: %d transactions", len(all_txns))

    if skipped_symbols:
        log.warning("Skipped %d symbols (no CIK): %s", len(skipped_symbols), skipped_symbols)

    if not all_txns:
        log.warning("No transactions fetched")
        return

    log.info("Fetched %d total P/S transactions — building DataFrame…", len(all_txns))

    new_data = pd.DataFrame(all_txns)
    new_data = new_data.sort_values("_date").reset_index(drop=True)
    # Add nanosecond offsets to deduplicate same-date filing timestamps
    new_data["_date"] = new_data["_date"] + pd.to_timedelta(new_data.index, unit="ns")
    new_data = new_data.set_index("_date")
    new_data.index.name = "filing_date"

    # Merge: SEC fills historical period, FMP wins for recent period
    if not existing.empty:
        # Keep SEC rows only before existing FMP data starts
        sec_historical = new_data[new_data.index < existing.index.min()]
        combined = pd.concat([sec_historical, existing]).sort_index()
        log.info(
            "Merged: %d SEC historical rows + %d existing FMP rows = %d total",
            len(sec_historical),
            len(existing),
            len(combined),
        )
    else:
        combined = new_data
        log.info("No existing data — writing %d rows", len(combined))

    store.write_series(ARC_LIB, ARC_KEY, combined)
    log.info(
        "Wrote %d rows to %s/%s  (%s → %s)",
        len(combined),
        ARC_LIB,
        ARC_KEY,
        combined.index.min().date(),
        combined.index.max().date(),
    )
    log.info("SEC insider backfill complete")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Backfill insider trades from SEC EDGAR Form 4")
    parser.add_argument(
        "--start",
        default="2006-01-01",
        help="Start date YYYY-MM-DD (default: 2006-01-01)",
    )
    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=UTC)
    log.info(
        "Backfilling SEC Form 4 insider trades from %s for %d symbols",
        start_dt.date(),
        len(SYMBOLS),
    )
    ingest(start_dt)
