"""Export ArcticDB bars to parquet for consumption by the quant sandbox."""
import logging
from pathlib import Path

from data.store import get_store

logger = logging.getLogger(__name__)

LIBRARIES = ["crypto", "futures"]
DEFAULT_EXPORT_DIR = Path.home() / "quant-research" / "data"


def export_all(export_dir: Path = DEFAULT_EXPORT_DIR) -> None:
    store = get_store()
    for library in LIBRARIES:
        lib_dir = export_dir / library
        lib_dir.mkdir(parents=True, exist_ok=True)
        symbols = store.list_symbols(library)
        for symbol in symbols:
            df = store.read_bars(library, symbol)
            safe_name = symbol.replace("/", "_").replace(" ", "_")
            out = lib_dir / f"{safe_name}.parquet"
            df.to_parquet(out)
            logger.info("Exported %s/%s → %s (%d rows)", library, symbol, out, len(df))
