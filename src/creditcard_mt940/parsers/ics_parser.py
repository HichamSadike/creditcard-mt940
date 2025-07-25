"""ICS credit card CSV parser with sign flipping logic."""

import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from dataclasses import dataclass

from .base_parser import BaseParser
from ..mt940.formatter import Transaction


@dataclass
class RawTransaction:
    """Raw transaction data from ICS CSV."""
    transaction_date: datetime
    booking_date: datetime
    description: str
    cardholder_name: str
    card_number: str
    debit_credit: str  # 'D' for debit, 'C' for credit
    amount: Decimal
    merchant_category: Optional[str] = None
    country: Optional[str] = None
    currency: str = "EUR"
    original_amount: Optional[Decimal] = None
    transaction_type: Optional[str] = None
    wallet_provider: Optional[str] = None


class IcsParser(BaseParser):
    """Parser for ICS credit card CSV files with sign flipping logic."""
    
    def __init__(self):
        super().__init__()
        self.settlement_keywords = ["geincasseerd vorig saldo", "verrekening vorig saldo"]
    
    def get_bank_name(self) -> str:
        return "ICS"
    
    def get_supported_file_types(self) -> List[str]:
        return ["csv"]
    
    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse ICS CSV file and return list of transactions."""
        # Try different encodings for ICS files
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'utf-8-sig']:
            try:
                df = pd.read_csv(file_path, sep=';', encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not decode CSV file with any supported encoding")
        
        # Clean column names (remove BOM and whitespace issues)
        df.columns = [col.replace('\ufeff', '').replace('\xa0', ' ').strip() for col in df.columns]
        
        # Parse raw transactions
        raw_transactions = self._parse_raw_transactions(df)
        
        # Apply ICS-specific business rules
        processed_transactions = self._apply_business_rules(raw_transactions)
        
        return processed_transactions
    
    def _parse_raw_transactions(self, df: pd.DataFrame) -> List[RawTransaction]:
        """Parse raw transactions from DataFrame."""
        raw_transactions = []
        
        for index, row in df.iterrows():
            # Skip empty rows or rows with missing essential data
            if pd.isna(row.get('Omschrijving', '')) or pd.isna(row.get('Bedrag', '')):
                continue
                
            # Parse transaction date (DD-MM-YYYY format)
            trans_date_str = str(row['Transactiedatum']).strip()
            try:
                transaction_date = datetime.strptime(trans_date_str, '%d-%m-%Y')
            except ValueError:
                print(f"Warning: Invalid transaction date format in row {index}: {trans_date_str}")
                continue
            
            # Parse booking date (DD-MM-YYYY format)
            booking_date_str = str(row['Boekingsdatum']).strip()
            try:
                booking_date = datetime.strptime(booking_date_str, '%d-%m-%Y')
            except ValueError:
                booking_date = transaction_date  # Fallback to transaction date
            
            # Parse amount (European format with comma as decimal separator and dot as thousand separator)
            amount_str = str(row['Bedrag']).strip()
            # Handle European format: 1.234,56 -> 1234.56
            if ',' in amount_str and '.' in amount_str:
                # Both comma and dot present: dot is thousands separator, comma is decimal
                amount_str = amount_str.replace('.', '').replace(',', '.')
            elif ',' in amount_str:
                # Only comma present: comma is decimal separator
                amount_str = amount_str.replace(',', '.')
            
            try:
                amount = Decimal(amount_str)
            except:
                print(f"Warning: Invalid amount format in row {index}: {amount_str}")
                continue
            
            # Parse description
            description = str(row['Omschrijving']).strip()
            
            # Parse debit/credit indicator
            debit_credit = str(row.get('Debit/Credit', '')).strip().upper()
            
            # Parse optional fields
            original_amount = None
            if pd.notna(row.get('Bedrag in oorspronkelijke valuta')) and str(row['Bedrag in oorspronkelijke valuta']).strip():
                try:
                    original_amount = Decimal(str(row['Bedrag in oorspronkelijke valuta']).replace(',', '.'))
                except:
                    pass
            
            raw_transaction = RawTransaction(
                transaction_date=transaction_date,
                booking_date=booking_date,
                description=description,
                cardholder_name=str(row.get('Naam Card-houder', '')).strip(),
                card_number=str(row.get('Card nummer', '')).strip(),
                debit_credit=debit_credit,
                amount=amount,
                merchant_category=str(row.get('Merchant categorie', '')).strip() if pd.notna(row.get('Merchant categorie')) else None,
                country=str(row.get('Land', '')).strip() if pd.notna(row.get('Land')) else None,
                currency=str(row.get('Valuta', 'EUR')).strip(),
                original_amount=original_amount,
                transaction_type=str(row.get('Type transactie', '')).strip() if pd.notna(row.get('Type transactie')) else None,
                wallet_provider=str(row.get('WalletProvider', '')).strip() if pd.notna(row.get('WalletProvider')) and str(row.get('WalletProvider')).strip() != 'null' else None
            )
            
            raw_transactions.append(raw_transaction)
        
        return raw_transactions
    
    def _apply_business_rules(self, raw_transactions: List[RawTransaction]) -> List[Transaction]:
        """Apply ICS-specific business rules with sign flipping."""
        processed_transactions = []
        
        for i, raw_transaction in enumerate(raw_transactions):
            # Check if this is a settlement from previous statement
            if self._is_previous_statement_settlement(raw_transaction):
                # Settlements should be positive (already handled by sign flipping logic)
                processed_amount, transaction_type = self._apply_ics_sign_logic(raw_transaction)
                
                settlement_transaction = Transaction(
                    date=raw_transaction.transaction_date,
                    amount=processed_amount,
                    description="Settlement previous statement",
                    counter_account=f"ICS{raw_transaction.card_number}",
                    reference=f"{50000000000 + i + 1}",  # ICS reference format
                    transaction_type="CREDIT"
                )
                processed_transactions.append(settlement_transaction)
                continue
            
            # Apply ICS sign flipping logic
            processed_amount, transaction_type = self._apply_ics_sign_logic(raw_transaction)
            
            # Generate counter account using card number
            counter_account = f"NL00ICS0{raw_transaction.card_number.replace('*', '0')}"
            
            # Generate reference ID
            reference = f"{50000000000 + i + 1}"  # Start from 50000000001 for ICS
            
            transaction = Transaction(
                date=raw_transaction.transaction_date,
                amount=processed_amount,
                description=raw_transaction.description,
                counter_account=counter_account,
                reference=reference,
                transaction_type=transaction_type
            )
            
            processed_transactions.append(transaction)
        
        return processed_transactions
    
    def _apply_ics_sign_logic(self, transaction: RawTransaction) -> tuple:
        """Apply ICS-specific sign flipping logic based on Debit/Credit indicator."""
        # ICS sign flipping logic:
        # - Debit (D) transactions: flip to negative (purchases)
        # - Credit (C) transactions: flip to positive (payments/settlements)
        
        if transaction.debit_credit == 'C':
            # Credit transactions: flip sign (usually negative amounts become positive)
            return -transaction.amount, "CREDIT"
        elif transaction.debit_credit == 'D':
            # Debit transactions: flip sign (usually positive amounts become negative)
            return -transaction.amount, "TRANSFER"
        else:
            # Unknown type, keep as is but classify as transfer
            return transaction.amount, "TRANSFER"
    
    def _is_previous_statement_settlement(self, transaction: RawTransaction) -> bool:
        """Check if transaction is a settlement from previous statement."""
        description_lower = transaction.description.lower()
        return any(keyword in description_lower for keyword in self.settlement_keywords)
    
    def get_account_info(self, file_path: str) -> dict:
        """Extract account information from ICS CSV."""
        # Try different encodings for ICS files
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'utf-8-sig']:
            try:
                df = pd.read_csv(file_path, sep=';', encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not decode CSV file with any supported encoding")
        
        # Clean column names
        df.columns = [col.replace('\ufeff', '').replace('\xa0', ' ').strip() for col in df.columns]
        
        # Try to extract dates to determine range
        dates = []
        for _, row in df.iterrows():
            if pd.notna(row.get('Transactiedatum')):
                try:
                    date_str = str(row['Transactiedatum']).strip()
                    date = datetime.strptime(date_str, '%d-%m-%Y')
                    dates.append(date)
                except ValueError:
                    continue
        
        min_date = min(dates) if dates else datetime.now()
        max_date = max(dates) if dates else datetime.now()
        
        # Use first card number found for account
        account_number = "NL00ICS0000000000"  # Default
        for _, row in df.iterrows():
            if pd.notna(row.get('Card nummer')):
                card_num = str(row['Card nummer']).strip()
                account_number = f"NL00ICS0{card_num.replace('*', '0')}"
                break
        
        return {
            'account_number': account_number,
            'start_date': min_date,
            'end_date': max_date
        }
    
    def validate_file_format(self, file_path: str) -> dict:
        """Validate ICS CSV file format and return validation results."""
        try:
            import pandas as pd
            
            # Try to read the CSV with different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'utf-8-sig']:
                try:
                    df = pd.read_csv(file_path, sep=';', encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return {
                    'valid': False,
                    'error': "Could not decode CSV file with any supported encoding",
                    'columns_found': []
                }
            
            # Clean column names
            df.columns = [col.replace('\ufeff', '').replace('\xa0', ' ').strip() for col in df.columns]
            
            # Check required columns for ICS format
            required_columns = [
                'Transactiedatum',
                'Omschrijving',
                'Debit/Credit', 
                'Bedrag'
            ]
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    'valid': False,
                    'error': f"Missing required columns: {', '.join(missing_columns)}",
                    'columns_found': list(df.columns)
                }
            
            # Check if we have any data
            if len(df) == 0:
                return {
                    'valid': False,
                    'error': "CSV file is empty",
                    'columns_found': list(df.columns)
                }
            
            # Try to parse a few transactions to check format
            validation_errors = []
            
            for index, row in df.head(5).iterrows():
                # Check date format (DD-MM-YYYY)
                try:
                    datetime.strptime(str(row['Transactiedatum']), '%d-%m-%Y')
                except ValueError:
                    validation_errors.append(f"Invalid date format in row {index}: {row['Transactiedatum']}")
                
                # Check amount format
                try:
                    Decimal(str(row['Bedrag']).replace(',', '.'))
                except:
                    validation_errors.append(f"Invalid amount format in row {index}: {row['Bedrag']}")
                
                # Check debit/credit indicator
                debit_credit = str(row.get('Debit/Credit', '')).strip().upper()
                if debit_credit not in ['D', 'C']:
                    validation_errors.append(f"Invalid Debit/Credit indicator in row {index}: {debit_credit}")
            
            if validation_errors:
                return {
                    'valid': False,
                    'error': "Format validation errors: " + "; ".join(validation_errors),
                    'columns_found': list(df.columns)
                }
            
            return {
                'valid': True,
                'message': f"ICS CSV file is valid with {len(df)} transactions",
                'columns_found': list(df.columns),
                'row_count': len(df)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Error reading ICS CSV file: {str(e)}",
                'columns_found': []
            }