"""Generic Excel transaction parser for manual transaction entry."""

import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import List

from .base_parser import BaseParser
from ..mt940.formatter import Transaction


# Required columns in the Excel template
REQUIRED_COLUMNS = [
    "Datum",
    "Bedrag",
    "Omschrijving",
    "Tegenrekening",
    "Referentie",
]


class ExcelParser(BaseParser):
    """Parser for generic Excel transaction files (user-filled template)."""

    def get_bank_name(self) -> str:
        return "Excel (Handmatig)"

    def get_supported_file_types(self) -> List[str]:
        return ["xlsx", "xls"]

    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse Excel template file and return list of transactions."""
        df = pd.read_excel(file_path)

        # Normalize column names (strip whitespace)
        df.columns = [col.strip() for col in df.columns]

        transactions = []

        for index, row in df.iterrows():
            # Skip empty rows
            if pd.isna(row.get("Datum")) or pd.isna(row.get("Bedrag")):
                continue

            # Parse date — support multiple formats
            date = self._parse_date(row["Datum"], index)
            if date is None:
                continue

            # Parse amount
            amount = self._parse_amount(row["Bedrag"], index)
            if amount is None:
                continue

            # Description (required)
            description = str(row.get("Omschrijving", "")).strip()
            if not description:
                print(f"Warning: Empty description in row {index}, skipping")
                continue

            # Optional fields
            counter_account = str(row.get("Tegenrekening", "")).strip()
            if not counter_account or counter_account == "nan":
                counter_account = None

            reference = str(row.get("Referentie", "")).strip()
            if not reference or reference == "nan":
                reference = f"EXCEL_{index:06d}"

            transaction = Transaction(
                date=date,
                amount=amount,
                description=description,
                counter_account=counter_account,
                reference=reference,
                transaction_type=self._classify_transaction(amount),
            )
            transactions.append(transaction)

        return transactions

    def _parse_date(self, value, row_index: int):
        """Parse date from various formats."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()

        date_str = str(value).strip()
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        print(f"Warning: Invalid date format in row {row_index}: {date_str}")
        return None

    def _parse_amount(self, value, row_index: int):
        """Parse amount from various formats."""
        if isinstance(value, (int, float)):
            return Decimal(str(value))

        amount_str = str(value).strip().replace(",", ".")
        # Remove currency symbols
        for sym in ("€", "$", "EUR"):
            amount_str = amount_str.replace(sym, "").strip()

        try:
            return Decimal(amount_str)
        except Exception:
            print(f"Warning: Invalid amount in row {row_index}: {value}")
            return None

    def _classify_transaction(self, amount: Decimal) -> str:
        """Classify transaction type based on amount sign."""
        if amount > 0:
            return "CREDIT"
        return "TRANSFER"

    def get_account_info(self, file_path: str) -> dict:
        """Extract account information from Excel file."""
        df = pd.read_excel(file_path)
        df.columns = [col.strip() for col in df.columns]

        dates = []
        for _, row in df.iterrows():
            if pd.notna(row.get("Datum")):
                date = self._parse_date(row["Datum"], 0)
                if date:
                    dates.append(date)

        min_date = min(dates) if dates else datetime.now()
        max_date = max(dates) if dates else datetime.now()

        return {
            "account_number": "NL00BANK0000000000",
            "start_date": min_date,
            "end_date": max_date,
        }

    def validate_file_format(self, file_path: str) -> dict:
        """Validate Excel file format."""
        try:
            df = pd.read_excel(file_path)
            df.columns = [col.strip() for col in df.columns]

            # Check required columns
            missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
            if missing:
                return {
                    "valid": False,
                    "error": f"Ontbrekende kolommen: {', '.join(missing)}. "
                    f"Download het template via de sidebar.",
                    "columns_found": list(df.columns),
                }

            if len(df) == 0:
                return {
                    "valid": False,
                    "error": "Excel bestand bevat geen transacties.",
                    "columns_found": list(df.columns),
                }

            # Validate a few rows
            errors = []
            for index, row in df.head(5).iterrows():
                if pd.isna(row.get("Datum")):
                    continue
                if self._parse_date(row["Datum"], index) is None:
                    errors.append(
                        f"Ongeldig datumformaat in rij {index + 2}: {row['Datum']}"
                    )
                if pd.notna(row.get("Bedrag")) and self._parse_amount(row["Bedrag"], index) is None:
                    errors.append(
                        f"Ongeldig bedrag in rij {index + 2}: {row['Bedrag']}"
                    )

            if errors:
                return {
                    "valid": False,
                    "error": "; ".join(errors),
                    "columns_found": list(df.columns),
                }

            # Count actual data rows (non-empty)
            data_rows = df.dropna(subset=["Datum", "Bedrag"]).shape[0]

            return {
                "valid": True,
                "message": f"Excel bestand is geldig met {data_rows} transacties",
                "columns_found": list(df.columns),
                "row_count": data_rows,
            }

        except Exception as e:
            return {
                "valid": False,
                "error": f"Fout bij lezen Excel bestand: {str(e)}",
                "columns_found": [],
            }
