"""AMEX credit card Excel parser with payment reversal logic."""

import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import List

from .base_parser import BaseParser
from ..mt940.formatter import Transaction


class AmexParser(BaseParser):
    """Parser for AMEX credit card Excel files."""
    
    def __init__(self):
        super().__init__()
        self.payment_keywords = ["hartelijk bedankt voor uw betaling"]
    
    def get_bank_name(self) -> str:
        return "AMEX"
    
    def get_supported_file_types(self) -> List[str]:
        return ["xlsx", "xls"]
    
    # Known AMEX Excel column mappings (by header name)
    COLUMN_MAP = {
        'datum': 'date',
        'date': 'date',
        'omschrijving': 'description',
        'description': 'description',
        'bedrag': 'amount',
        'amount': 'amount',
        'vermeld op uw rekeningoverzicht als': 'statement_description',
        'adres': 'address',
        'address': 'address',
        'aanvullende informatie': 'extra_info',
        'referentie': 'reference',
        'reference': 'reference',
        'plaats': 'city',
        'postcode': 'postal_code',
        'land': 'country',
    }

    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse AMEX Excel file and return list of transactions."""
        # First pass: read without header to scan for the real header row
        try:
            df_raw = pd.read_excel(file_path, engine='openpyxl', header=None)
        except:
            df_raw = pd.read_excel(file_path, engine='xlrd', header=None)
        
        transactions = []
        
        # Find the header row by looking for known AMEX column names
        header_row = self._find_header_row(df_raw)
        
        # Re-read with proper header (or default row 0 if no special header found)
        read_header = header_row if header_row is not None else 0
        try:
            df = pd.read_excel(file_path, engine='openpyxl', header=read_header)
        except:
            df = pd.read_excel(file_path, engine='xlrd', header=read_header)
        
        # Standardize column names (AMEX files might have different column names)
        df.columns = [str(col).strip() for col in df.columns]
        
        # Build a mapping from semantic role -> column index using COLUMN_MAP
        self._col_indices = {}
        for idx, col_name in enumerate(df.columns):
            role = self.COLUMN_MAP.get(col_name.lower())
            if role and role not in self._col_indices:
                self._col_indices[role] = idx
        
        for index, row in df.iterrows():
            # Skip empty rows
            if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip() == '':
                continue
            
            # Try to extract transaction data (AMEX format can vary)
            transaction = self._parse_amex_row(row, index)
            if transaction:
                transactions.append(transaction)
        
        return transactions
    
    def _find_header_row(self, df: pd.DataFrame) -> int:
        """Find the header row in AMEX Excel file."""
        # Look for common AMEX headers
        common_headers = ['date', 'datum', 'amount', 'bedrag', 'description', 'omschrijving', 'transaction']
        
        for idx, row in df.iterrows():
            row_str = ' '.join(str(cell).lower() for cell in row if pd.notna(cell))
            if any(header in row_str for header in common_headers):
                return idx
        
        return None
    
    def _parse_amex_row(self, row: pd.Series, index: int) -> Transaction:
        """Parse a single AMEX row into a Transaction."""
        try:
            # AMEX Excel structure: assume standard format with amount in column 3 (index 2)
            # Try to identify date column (usually first column)
            date = None
            date_col_idx = 0
            if pd.notna(row.iloc[date_col_idx]):
                try:
                    date = self._parse_date(row.iloc[date_col_idx])
                except:
                    # If first column is not date, try second column
                    date_col_idx = 1
                    if len(row) > 1 and pd.notna(row.iloc[date_col_idx]):
                        try:
                            date = self._parse_date(row.iloc[date_col_idx])
                        except:
                            date = None
            
            if not date:
                return None
            
            # Amount is expected to be in column 3 (index 2) - the "Bedrag" column
            amount = None
            amount_col_idx = 2
            if len(row) > amount_col_idx and pd.notna(row.iloc[amount_col_idx]):
                try:
                    amount = self._clean_amount(row.iloc[amount_col_idx])
                except:
                    # If column 3 doesn't work, try to find amount in other columns
                    for i in range(len(row)):
                        if pd.notna(row.iloc[i]):
                            try:
                                amount = self._clean_amount(row.iloc[i])
                                amount_col_idx = i
                                break
                            except:
                                continue
            
            if amount is None:
                return None
            
            # Get description using column map priority:
            # 1. "Vermeld op uw rekeningoverzicht als" (statement_description) — what the bookkeeper sees
            # 2. "Omschrijving" (description) — original transaction description
            # 3. Fallback: longest non-date/non-amount text column
            description = ""
            col_indices = getattr(self, '_col_indices', {})
            for role in ('statement_description', 'description'):
                idx = col_indices.get(role)
                if idx is not None and idx < len(row) and pd.notna(row.iloc[idx]):
                    candidate = str(row.iloc[idx]).strip()
                    if candidate:
                        description = candidate
                        break
            
            if not description:
                # Fallback: find longest text column (excluding date, amount, and address)
                address_idx = col_indices.get('address')
                for i in range(len(row)):
                    if i in (date_col_idx, amount_col_idx) or i == address_idx:
                        continue
                    if pd.notna(row.iloc[i]):
                        cell_str = str(row.iloc[i]).strip()
                        if cell_str and not self._looks_like_date_or_amount(cell_str):
                            if len(cell_str) > len(description):
                                description = cell_str
            
            if not description:
                description = f"AMEX Transaction {index + 1}"
            
            # Apply AMEX-specific business logic
            processed_amount, transaction_type = self._apply_amex_logic(amount, description)
            
            # Generate reference ID in Rabobank format (numeric sequence)
            reference = f"{49000000000 + index + 1}"  # Start from 49000000001 like Rabobank
            
            return Transaction(
                date=date,
                amount=processed_amount,
                description=description,
                counter_account="NL00AMEX0000000000",  # Use IBAN-like format for consistency
                reference=reference,
                transaction_type=transaction_type
            )
            
        except Exception as e:
            print(f"Warning: Could not parse AMEX row {index}: {e}")
            return None
    
    def _apply_amex_logic(self, amount: Decimal, description: str) -> tuple:
        """Apply AMEX-specific business logic with Rabobank-compatible transaction types."""
        description_lower = description.lower()
        
        # Check if this is a payment to AMEX (should be positive)
        if any(keyword in description_lower for keyword in self.payment_keywords):
            return abs(amount), "CREDIT"  # Make positive, keep as CREDIT
        
        # All other transactions should have their sign flipped (+ becomes -, - becomes +)
        return -amount, "TRANSFER"  # Flip sign, use TRANSFER for N544 code like Rabobank
    
    def _parse_date(self, date_value) -> datetime:
        """Parse date from various formats."""
        if isinstance(date_value, datetime):
            return date_value
        elif pd.isna(date_value):
            raise ValueError("Date value is NaN")
        
        # Convert to string and try different formats
        date_str = str(date_value).strip()
        
        # Try common date formats
        for date_format in ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y']:
            try:
                return datetime.strptime(date_str, date_format)
            except ValueError:
                continue
        
        # Try pandas timestamp parsing as fallback
        try:
            return pd.to_datetime(date_value).to_pydatetime()
        except:
            raise ValueError(f"Could not parse date: {date_value}")
    
    def _clean_amount(self, amount_value) -> Decimal:
        """Clean and convert amount to Decimal."""
        if pd.isna(amount_value):
            raise ValueError("Amount value is NaN")
        
        # Convert to string and clean
        amount_str = str(amount_value).strip()
        
        # Remove currency symbols and clean
        amount_str = amount_str.replace('€', '').replace('$', '').replace(',', '.').strip()
        
        # Remove any non-numeric characters except decimal point and minus
        cleaned = ''.join(c for c in amount_str if c.isdigit() or c in '.-')
        
        if not cleaned or cleaned == '-':
            raise ValueError(f"Invalid amount format: {amount_value}")
        
        return Decimal(cleaned)
    
    def _looks_like_date_or_amount(self, text: str) -> bool:
        """Check if text looks like a date or amount."""
        # Check if it looks like an amount (has digits and decimal/comma)
        if any(c.isdigit() for c in text) and any(c in '.,€$-' for c in text):
            return True
        
        # Check if it looks like a date (has digits and date separators)
        if any(c.isdigit() for c in text) and any(c in '/-' for c in text):
            return True
        
        return False
    
    def _generate_reference_id(self, date: datetime, sequence: int) -> str:
        """Generate reference ID for AMEX transaction in Rabobank format."""
        # Use numeric format like Rabobank: 49000000001, 49000000002, etc.
        return f"{49000000000 + sequence}"
    
    def get_account_info(self, file_path: str) -> dict:
        """Extract account information from AMEX Excel."""
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
        except:
            df = pd.read_excel(file_path, engine='xlrd')
        
        # Try to extract dates to determine range
        dates = []
        for _, row in df.iterrows():
            # Try first two columns for dates (standard AMEX format)
            for col_idx in [0, 1]:
                if col_idx < len(row) and pd.notna(row.iloc[col_idx]):
                    try:
                        date = self._parse_date(row.iloc[col_idx])
                        dates.append(date)
                        break  # Found date in this row, move to next row
                    except:
                        continue
        
        min_date = min(dates) if dates else datetime.now()
        max_date = max(dates) if dates else datetime.now()
        
        return {
            'account_number': 'NL00AMEX0000000000',  # Use IBAN-like format for MT940 compatibility
            'start_date': min_date,
            'end_date': max_date
        }
    
    def validate_file_format(self, file_path: str) -> dict:
        """Validate AMEX Excel file format and return validation results."""
        try:
            # Check file extension
            if not file_path.lower().endswith(('.xlsx', '.xls')):
                return {
                    'valid': False,
                    'error': "File must be an Excel file (.xlsx or .xls)",
                    'columns_found': []
                }
            
            # Try to read the Excel file
            try:
                df = pd.read_excel(file_path, engine='openpyxl')
            except:
                try:
                    df = pd.read_excel(file_path, engine='xlrd')
                except:
                    return {
                        'valid': False,
                        'error': "Could not read Excel file. Please ensure it's a valid Excel format.",
                        'columns_found': []
                    }
            
            # Check if we have any data
            if len(df) == 0:
                return {
                    'valid': False,
                    'error': "Excel file is empty",
                    'columns_found': list(df.columns)
                }
            
            # Try to find at least one valid transaction
            found_valid_transaction = False
            for index, row in df.iterrows():
                if self._parse_amex_row(row, index):
                    found_valid_transaction = True
                    break
            
            if not found_valid_transaction:
                return {
                    'valid': False,
                    'error': "No valid transactions found in AMEX Excel file. Expected: Date in column 1, Amount in column 3.",
                    'columns_found': list(df.columns)
                }
            
            return {
                'valid': True,
                'message': f"AMEX Excel file is valid with {len(df)} rows",
                'columns_found': list(df.columns),
                'row_count': len(df)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Error reading AMEX Excel file: {str(e)}",
                'columns_found': []
            }