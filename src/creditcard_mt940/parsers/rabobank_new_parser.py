"""Rabobank credit card CSV parser for new format with business rules."""

import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from dataclasses import dataclass

from .base_parser import BaseParser
from ..mt940.formatter import Transaction


@dataclass
class RawTransaction:
    """Raw transaction data from new CSV format."""
    counter_account: str
    reference: str
    date: datetime
    amount: Decimal
    description: str
    currency: str = "EUR"
    credit_card_number: str = ""
    product_name: str = ""
    original_amount: Optional[Decimal] = None
    original_currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None


class RabobankNewParser(BaseParser):
    """Parser for new Rabobank credit card CSV files with business rules."""
    
    def __init__(self):
        super().__init__()
        self.exchange_rate_keywords = ["koersopslag"]
        self.settlement_keywords = ["verrekening vorig overzicht"]
        self.ignored_keywords = ["monthly payment memo"]
    
    def get_bank_name(self) -> str:
        return "Rabobank"
    
    def get_supported_file_types(self) -> List[str]:
        return ["csv"]
    
    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse new format Rabobank CSV file and return list of transactions."""
        # Try different encodings for Rabobank files
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(file_path, sep=',', encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not decode CSV file with any supported encoding")
        
        # Clean column names (remove non-breaking spaces and other whitespace issues)
        df.columns = [col.replace('\xa0', ' ').strip() for col in df.columns]
        
        # Parse raw transactions
        raw_transactions = self._parse_raw_transactions(df)
        
        # Apply Rabobank-specific business rules
        processed_transactions = self._apply_business_rules(raw_transactions)
        
        return processed_transactions
    
    def _parse_raw_transactions(self, df: pd.DataFrame) -> List[RawTransaction]:
        """Parse raw transactions from DataFrame."""
        raw_transactions = []
        
        for index, row in df.iterrows():
            # Skip empty rows or rows with missing essential data
            if pd.isna(row.get('Description', '')) or pd.isna(row.get('Amount', '')):
                continue
                
            # Parse date (YYYY-MM-DD format)
            date_str = str(row['Date']).strip()
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                print(f"Warning: Invalid date format in row {index}: {date_str}")
                continue
            
            # Parse amount (European format with comma as decimal separator)
            amount_str = str(row['Amount']).replace(',', '.')
            try:
                amount = Decimal(amount_str)
            except:
                print(f"Warning: Invalid amount format in row {index}: {amount_str}")
                continue
            
            # Parse description
            description = str(row['Description']).strip()
            
            # Skip if this is the final indicator row (Monthly Payment memo)
            if any(keyword.lower() in description.lower() for keyword in self.ignored_keywords):
                continue
            
            # Parse optional fields
            original_amount = None
            original_currency = None
            exchange_rate = None
            
            if pd.notna(row.get('Instr Amt')) and str(row['Instr Amt']).strip():
                try:
                    original_amount = Decimal(str(row['Instr Amt']).replace(',', '.'))
                except:
                    pass
            
            if pd.notna(row.get('Instr Ccy')) and str(row['Instr Ccy']).strip():
                original_currency = str(row['Instr Ccy']).strip()
            
            if pd.notna(row.get('Rate')) and str(row['Rate']).strip():
                try:
                    exchange_rate = Decimal(str(row['Rate']).replace(',', '.'))
                except:
                    pass
            
            raw_transaction = RawTransaction(
                counter_account=str(row['Counterpty IBAN']).strip(),
                reference=str(row['Transaction Reference']).strip(),
                date=date,
                amount=amount,
                description=description,
                currency=str(row.get('Ccy', 'EUR')).strip(),
                credit_card_number=str(row.get('Credit Card Number', '')).strip(),
                product_name=str(row.get('Product Name', '')).strip(),
                original_amount=original_amount,
                original_currency=original_currency,
                exchange_rate=exchange_rate
            )
            
            raw_transactions.append(raw_transaction)
        
        return raw_transactions
    
    def _apply_business_rules(self, raw_transactions: List[RawTransaction]) -> List[Transaction]:
        """Apply Rabobank-specific business rules to raw transactions."""
        processed_transactions = []
        i = 0
        
        while i < len(raw_transactions):
            current_transaction = raw_transactions[i]
            
            # Check if this is an exchange rate surcharge
            if self._is_exchange_rate_surcharge(current_transaction):
                # Skip standalone exchange rate surcharge - it should be combined with previous transaction
                i += 1
                continue
            
            # Check if this is a settlement from previous statement
            if self._is_previous_statement_settlement(current_transaction):
                # Convert to positive amount as per business rules
                settlement_transaction = Transaction(
                    date=current_transaction.date,
                    amount=abs(current_transaction.amount),  # Make positive
                    description=f"Settlement previous statement",
                    counter_account=current_transaction.counter_account,
                    reference=current_transaction.reference,
                    transaction_type="CREDIT"
                )
                processed_transactions.append(settlement_transaction)
                i += 1
                continue
            
            # Check if next transaction is an exchange rate surcharge for this transaction
            combined_amount = current_transaction.amount
            description = current_transaction.description
            
            if (i + 1 < len(raw_transactions) and 
                self._is_exchange_rate_surcharge(raw_transactions[i + 1]) and
                self._transactions_are_related(current_transaction, raw_transactions[i + 1])):
                
                # Combine amounts (both should be negative, so adding them gives the total)
                combined_amount += raw_transactions[i + 1].amount
                description = f"{description} (incl. exchange rate surcharge)"
                i += 1  # Skip the next transaction as it's been combined
            
            # Create processed transaction with proper classification
            transaction = Transaction(
                date=current_transaction.date,
                amount=combined_amount,
                description=description,
                counter_account=current_transaction.counter_account,
                reference=current_transaction.reference,
                transaction_type=self._classify_transaction(current_transaction)
            )
            
            processed_transactions.append(transaction)
            i += 1
        
        return processed_transactions
    
    def _is_exchange_rate_surcharge(self, transaction: RawTransaction) -> bool:
        """Check if transaction is an exchange rate surcharge."""
        description_lower = transaction.description.lower()
        return any(keyword in description_lower for keyword in self.exchange_rate_keywords)
    
    def _is_previous_statement_settlement(self, transaction: RawTransaction) -> bool:
        """Check if transaction is a settlement from previous statement."""
        description_lower = transaction.description.lower()
        return any(keyword in description_lower for keyword in self.settlement_keywords)
    
    def _transactions_are_related(self, transaction1: RawTransaction, transaction2: RawTransaction) -> bool:
        """Check if two transactions are related (same date, consecutive references)."""
        # Check if dates are the same
        if transaction1.date.date() != transaction2.date.date():
            return False
        
        # Check if references are consecutive (new format uses different reference pattern)
        try:
            ref1 = int(transaction1.reference)
            ref2 = int(transaction2.reference)
            return ref2 == ref1 + 1  # Exchange rate surcharge should be the next reference
        except ValueError:
            return False
    
    def _classify_transaction(self, transaction: RawTransaction) -> str:
        """Classify transaction type based on description and amount."""
        description = transaction.description.lower()
        
        # Credit card transactions (most common for credit card CSV)
        if any(keyword in description for keyword in ['apple pay', 'card', 'pos']):
            return "CARD"
        
        # Direct debits / automatic payments
        if any(keyword in description for keyword in ['incasso', 'automatische', 'subscription', 'recurring']):
            return "DIRECT_DEBIT"
        
        # Credits (positive amounts)
        if transaction.amount > 0:
            return "CREDIT"
        
        # Default to transfer for other transactions
        return "TRANSFER"
    
    def get_account_info(self, file_path: str) -> dict:
        """Extract account information from new format Rabobank CSV."""
        # Try different encodings for Rabobank files
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(file_path, sep=',', encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Could not decode CSV file with any supported encoding")
        
        # Clean column names (remove non-breaking spaces and other whitespace issues)
        df.columns = [col.replace('\xa0', ' ').strip() for col in df.columns]
        
        # Get account number from first row
        account_number = str(df.iloc[0]['Counterpty IBAN']).strip()
        
        # Get date range
        dates = []
        for _, row in df.iterrows():
            if pd.notna(row.get('Date')):
                try:
                    date_str = str(row['Date']).strip()
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                    dates.append(date)
                except ValueError:
                    continue
        
        min_date = min(dates) if dates else datetime.now()
        max_date = max(dates) if dates else datetime.now()
        
        return {
            'account_number': account_number,
            'start_date': min_date,
            'end_date': max_date
        }
    
    def validate_file_format(self, file_path: str) -> dict:
        """Validate new format Rabobank CSV file format and return validation results."""
        try:
            import pandas as pd
            
            # Try to read the CSV with different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, sep=',', encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return {
                    'valid': False,
                    'error': "Could not decode CSV file with any supported encoding",
                    'columns_found': []
                }
            
            # Clean column names (remove non-breaking spaces and other whitespace issues)
            df.columns = [col.replace('\xa0', ' ').strip() for col in df.columns]
            
            # Check required columns for new format
            required_columns = [
                'Counterpty IBAN',
                'Transaction Reference', 
                'Date',
                'Amount',
                'Description'
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
                # Check date format (YYYY-MM-DD)
                try:
                    datetime.strptime(str(row['Date']), '%Y-%m-%d')
                except ValueError:
                    validation_errors.append(f"Invalid date format in row {index}: {row['Date']}")
                
                # Check amount format
                try:
                    Decimal(str(row['Amount']).replace(',', '.'))
                except:
                    validation_errors.append(f"Invalid amount format in row {index}: {row['Amount']}")
            
            if validation_errors:
                return {
                    'valid': False,
                    'error': "Format validation errors: " + "; ".join(validation_errors),
                    'columns_found': list(df.columns)
                }
            
            return {
                'valid': True,
                'message': f"New format Rabobank CSV file is valid with {len(df)} transactions",
                'columns_found': list(df.columns),
                'row_count': len(df)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Error reading new format Rabobank CSV file: {str(e)}",
                'columns_found': []
            }