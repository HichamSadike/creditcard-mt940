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
            # Try to identify date column (usually first few columns)
            date = None
            for i in range(min(3, len(row))):
                if pd.notna(row.iloc[i]):
                    try:
                        # Try different date formats
                        date_str = str(row.iloc[i]).strip()
                        for date_format in ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y']:
                            try:
                                date = datetime.strptime(date_str, date_format)
                                break
                            except ValueError:
                                continue
                        if date:
                            break
                    except:
                        continue
            
            if not date:
                return None
            
            # Try to find amount column (look for numeric values)
            amount = None
            amount_col_idx = None
            for i in range(len(row)):
                if pd.notna(row.iloc[i]):
                    try:
                        amount_str = str(row.iloc[i]).replace(',', '.').replace('€', '').strip()
                        # Remove any non-numeric characters except decimal point and minus
                        amount_str = ''.join(c for c in amount_str if c.isdigit() or c in '.-')
                        if amount_str and amount_str != '-':
                            amount = Decimal(amount_str)
                            amount_col_idx = i
                            break
                    except:
                        continue
            
            if amount is None:
                return None
            
            # Try to find description column (usually text column after amount)
            description = ""
            for i in range(len(row)):
                if i != amount_col_idx and pd.notna(row.iloc[i]):
                    cell_str = str(row.iloc[i]).strip()
                    if cell_str and not cell_str.replace('.', '').replace(',', '').replace('-', '').isdigit():
                        if len(cell_str) > len(description):
                            description = cell_str
            
            if not description:
                description = f"AMEX Transaction {index}"
            
            # Apply AMEX-specific business logic
            processed_amount, transaction_type = self._apply_amex_logic(amount, description)
            
            return Transaction(
                date=date,
                amount=processed_amount,
                description=description,
                counter_account="AMEX",  # AMEX doesn't provide IBAN
                reference=f"AMEX_{index:06d}",
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
    
    def get_account_info(self, file_path: str) -> dict:
        """Extract account information from AMEX Excel."""
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
        except:
            df = pd.read_excel(file_path, engine='xlrd')
        
        # Try to extract dates to determine range
        dates = []
        for _, row in df.iterrows():
            for cell in row:
                if pd.notna(cell):
                    try:
                        date_str = str(cell).strip()
                        for date_format in ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y']:
                            try:
                                date = datetime.strptime(date_str, date_format)
                                dates.append(date)
                                break
                            except ValueError:
                                continue
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
            # Try to read the Excel file
            try:
                df = pd.read_excel(file_path, engine='openpyxl')
            except:
                df = pd.read_excel(file_path, engine='xlrd')
            
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
                    'error': "No valid transactions found in AMEX Excel file",
                    'columns_found': list(df.columns)
                }
            
            return {
                'valid': True,
                'message': f"AMEX Excel file is valid with data",
                'columns_found': list(df.columns),
                'row_count': len(df)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Error reading AMEX Excel file: {str(e)}",
                'columns_found': []
            }