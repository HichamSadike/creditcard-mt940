"""ING credit card CSV parser."""

import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import List

from .base_parser import BaseParser
from ..mt940.formatter import Transaction


class IngParser(BaseParser):
    """Parser for ING credit card CSV files."""
    
    def get_bank_name(self) -> str:
        return "ING"
    
    def get_supported_file_types(self) -> List[str]:
        return ["csv"]
    
    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse ING CSV file and return list of transactions."""
        df = pd.read_csv(file_path, sep=',', encoding='utf-8')
        
        transactions = []
        
        for index, row in df.iterrows():
            # Skip empty rows or rows with missing essential data
            if pd.isna(row.get('Omschrijving', '')) or pd.isna(row.get('Bedrag in EUR', '')):
                continue
            
            # Parse transaction date (YYYY-MM-DD format)
            date_str = str(row['Transactiedatum']).strip()
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                print(f"Warning: Invalid date format in row {index}: {date_str}")
                continue
            
            # Parse amount from "Bedrag in EUR" column (European format with comma as decimal separator)
            amount_str = str(row['Bedrag in EUR']).replace(',', '.')
            try:
                amount = Decimal(amount_str)
            except:
                print(f"Warning: Invalid amount format in row {index}: {amount_str}")
                continue
            
            # Parse description
            description = str(row['Omschrijving']).strip()
            
            # Get account number and card info (for reference, but use default IBAN)
            account_number = str(row['Accountnummer']).strip()
            card_number = str(row['Kaartnummer']).strip()

            # Create transaction with ING-specific classification using default IBAN
            transaction = Transaction(
                date=date,
                amount=amount,
                description=description,
                counter_account="NL98INGB1234567890",  # Use default IBAN for consistency
                reference=f"ING_{index:06d}",  # Generate reference since ING doesn't provide one
                transaction_type=self._classify_transaction(description, amount)
            )
            
            transactions.append(transaction)
        
        return transactions
    
    def _classify_transaction(self, description: str, amount: Decimal) -> str:
        """Classify ING transaction type based on description and amount."""
        description_lower = description.lower()
        
        # Credit transactions (positive amounts)
        if amount > 0:
            return "CREDIT"
        
        # Card transactions (most common for credit card CSV)
        if any(keyword in description_lower for keyword in ['betaalautomaat', 'apple pay', 'card', 'pos']):
            return "CARD"
        
        # Online transactions
        if any(keyword in description_lower for keyword in ['.com', 'online', 'paypal', 'ideal']):
            return "TRANSFER"
        
        # Default to transfer for other transactions
        return "TRANSFER"
    
    def get_account_info(self, file_path: str) -> dict:
        """Extract account information from ING CSV."""
        df = pd.read_csv(file_path, sep=',', encoding='utf-8')

        # Get date range from transaction dates
        dates = []
        for _, row in df.iterrows():
            if pd.notna(row.get('Transactiedatum')):
                try:
                    date_str = str(row['Transactiedatum']).strip()
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                    dates.append(date)
                except ValueError:
                    continue

        min_date = min(dates) if dates else datetime.now()
        max_date = max(dates) if dates else datetime.now()

        return {
            'account_number': 'NL98INGB1234567890',  # Use default IBAN for MT940 compatibility
            'start_date': min_date,
            'end_date': max_date
        }
    
    def validate_file_format(self, file_path: str) -> dict:
        """Validate ING CSV file format and return validation results."""
        try:
            # Try to read the CSV
            df = pd.read_csv(file_path, sep=',', encoding='utf-8')
            
            # Check required columns for ING format
            required_columns = [
                'Accountnummer',
                'Kaartnummer',
                'Naam op kaart',
                'Transactiedatum',
                'Boekingsdatum',
                'Omschrijving',
                'Bedrag in EUR'
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
                    datetime.strptime(str(row['Transactiedatum']), '%Y-%m-%d')
                except ValueError:
                    validation_errors.append(f"Invalid date format in row {index}: {row['Transactiedatum']}")
                
                # Check amount format
                try:
                    Decimal(str(row['Bedrag in EUR']).replace(',', '.'))
                except:
                    validation_errors.append(f"Invalid amount format in row {index}: {row['Bedrag in EUR']}")
            
            if validation_errors:
                return {
                    'valid': False,
                    'error': "Format validation errors: " + "; ".join(validation_errors),
                    'columns_found': list(df.columns)
                }
            
            return {
                'valid': True,
                'message': f"ING CSV file is valid with {len(df)} transactions",
                'columns_found': list(df.columns),
                'row_count': len(df)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Error reading ING CSV file: {str(e)}",
                'columns_found': []
            }