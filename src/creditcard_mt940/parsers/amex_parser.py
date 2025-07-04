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
    
    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse AMEX Excel file and return list of transactions."""
        # Read Excel file - try to auto-detect the correct sheet and format
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
        except:
            # Fallback to older Excel format
            df = pd.read_excel(file_path, engine='xlrd')
        
        transactions = []
        
        # Try to find the header row by looking for common AMEX column patterns
        header_row = self._find_header_row(df)
        if header_row is not None:
            # Re-read with proper header
            try:
                df = pd.read_excel(file_path, engine='openpyxl', header=header_row)
            except:
                df = pd.read_excel(file_path, engine='xlrd', header=header_row)
        
        # Standardize column names (AMEX files might have different column names)
        df.columns = [str(col).strip() for col in df.columns]
        
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
            
            # Try to find description column (usually after amount or in a text column)
            description = ""
            for i in range(len(row)):
                if i != date_col_idx and i != amount_col_idx and pd.notna(row.iloc[i]):
                    cell_str = str(row.iloc[i]).strip()
                    # Skip if it looks like a date or amount
                    if cell_str and not self._looks_like_date_or_amount(cell_str):
                        if len(cell_str) > len(description):
                            description = cell_str
            
            if not description:
                description = f"AMEX Transaction {index + 1}"
            
            # Apply AMEX-specific business logic
            processed_amount, transaction_type = self._apply_amex_logic(amount, description)
            
            # Generate reference ID
            reference = self._generate_reference_id(date, index + 1)
            
            return Transaction(
                date=date,
                amount=processed_amount,
                description=description,
                counter_account="AMEX",  # AMEX doesn't provide IBAN
                reference=reference,
                transaction_type=transaction_type
            )
            
        except Exception as e:
            print(f"Warning: Could not parse AMEX row {index}: {e}")
            return None
    
    def _apply_amex_logic(self, amount: Decimal, description: str) -> tuple:
        """Apply AMEX-specific business logic."""
        description_lower = description.lower()
        
        # Check if this is a payment to AMEX (should be positive)
        if any(keyword in description_lower for keyword in self.payment_keywords):
            return abs(amount), "CREDIT"  # Make positive
        
        # All other transactions should be negative (purchases)
        return -abs(amount), "CARD"  # Make negative
    
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
        """Generate reference ID for AMEX transaction."""
        return f"AMEX-{date.strftime('%Y%m%d')}-{sequence}"
    
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
            'account_number': 'AMEX',  # AMEX doesn't use IBAN format
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