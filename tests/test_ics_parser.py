"""Tests for ICS parser."""

import pytest
from decimal import Decimal
from datetime import datetime
from src.creditcard_mt940.parsers.ics_parser import IcsParser
from src.creditcard_mt940.mt940.formatter import Transaction


class TestIcsParser:
    """Test cases for IcsParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = IcsParser()
    
    def test_get_bank_name(self):
        """Test bank name."""
        assert self.parser.get_bank_name() == 'ICS'
    
    def test_get_supported_file_types(self):
        """Test supported file types."""
        assert self.parser.get_supported_file_types() == ['csv']
    
    def test_validate_file_format_valid(self, tmp_path):
        """Test validation with valid CSV."""
        csv_content = """Transactiedatum;Boekingsdatum;Omschrijving;Naam Card-houder;Card nummer;Debit/Credit;Bedrag;Merchant categorie;Land;Valuta;Bedrag in oorspronkelijke valuta;Type transactie;WalletProvider
30-06-2025;01-07-2025;UPWORK -822746539REF DUBLIN IRL;"Crombag, DMP";****4073;D;121,00;Employment Agencies;IRL;EUR;121,00;Transaction;null
28-06-2025;28-06-2025;GEINCASSEERD VORIG SALDO;"Crombag, DMP";****null;C;-1304,91;;;EUR;-1304,91;Payment;null"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is True
        assert 'ICS CSV file is valid' in result['message']
    
    def test_validate_file_format_missing_columns(self, tmp_path):
        """Test validation with missing required columns."""
        csv_content = """Transactiedatum;Omschrijving;Bedrag
30-06-2025;UPWORK TRANSACTION;121,00"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is False
        assert 'Missing required columns' in result['error']
    
    def test_parse_file_basic(self, tmp_path):
        """Test basic file parsing."""
        csv_content = """Transactiedatum;Boekingsdatum;Omschrijving;Naam Card-houder;Card nummer;Debit/Credit;Bedrag;Merchant categorie;Land;Valuta;Bedrag in oorspronkelijke valuta;Type transactie;WalletProvider
30-06-2025;01-07-2025;UPWORK -822746539REF DUBLIN IRL;"Crombag, DMP";****4073;D;121,00;Employment Agencies;IRL;EUR;121,00;Transaction;null
23-06-2025;24-06-2025;ADOBE  *ADOBE 044-207-3650 IRL;"Crombag, DMP";****4073;D;55,84;null;IRL;EUR;55,84;Transaction;null"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        
        # First transaction - Debit should become negative
        assert transactions[0].amount == Decimal('-121.00')
        assert transactions[0].description == 'UPWORK -822746539REF DUBLIN IRL'
        assert transactions[0].date == datetime(2025, 6, 30)
        assert transactions[0].transaction_type == 'TRANSFER'
        assert 'ICS' in transactions[0].counter_account
        
        # Second transaction - Debit should become negative
        assert transactions[1].amount == Decimal('-55.84')
        assert transactions[1].description == 'ADOBE  *ADOBE 044-207-3650 IRL'
        assert transactions[1].transaction_type == 'TRANSFER'
    
    def test_parse_file_with_credit_transaction(self, tmp_path):
        """Test parsing with credit transaction (sign flipping)."""
        csv_content = """Transactiedatum;Boekingsdatum;Omschrijving;Naam Card-houder;Card nummer;Debit/Credit;Bedrag;Merchant categorie;Land;Valuta;Bedrag in oorspronkelijke valuta;Type transactie;WalletProvider
30-06-2025;01-07-2025;UPWORK -822746539REF DUBLIN IRL;"Crombag, DMP";****4073;D;121,00;Employment Agencies;IRL;EUR;121,00;Transaction;null
28-06-2025;28-06-2025;GEINCASSEERD VORIG SALDO;"Crombag, DMP";****null;C;-1304,91;;;EUR;-1304,91;Payment;null"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        
        # First transaction - Debit (D) should become negative
        assert transactions[0].amount == Decimal('-121.00')
        assert transactions[0].transaction_type == 'TRANSFER'
        
        # Second transaction - Credit settlement (C) should become positive
        assert transactions[1].amount == Decimal('1304.91')  # Flipped from -1304.91
        assert transactions[1].transaction_type == 'CREDIT'
        assert transactions[1].description == 'Settlement previous statement'
    
    def test_sign_flipping_logic(self):
        """Test the sign flipping logic directly."""
        from src.creditcard_mt940.parsers.ics_parser import RawTransaction
        from datetime import datetime
        from decimal import Decimal
        
        # Test Debit transaction (should become negative)
        debit_transaction = RawTransaction(
            transaction_date=datetime(2025, 6, 30),
            booking_date=datetime(2025, 7, 1),
            description='UPWORK TRANSACTION',
            cardholder_name='Test User',
            card_number='****4073',
            debit_credit='D',
            amount=Decimal('121.00')
        )
        
        amount, trans_type = self.parser._apply_ics_sign_logic(debit_transaction)
        assert amount == Decimal('-121.00')
        assert trans_type == 'TRANSFER'
        
        # Test Credit transaction (should flip sign - negative becomes positive)
        credit_transaction = RawTransaction(
            transaction_date=datetime(2025, 6, 28),
            booking_date=datetime(2025, 6, 28),
            description='GEINCASSEERD VORIG SALDO',
            cardholder_name='Test User',
            card_number='****null',
            debit_credit='C',
            amount=Decimal('-1304.91')
        )
        
        amount, trans_type = self.parser._apply_ics_sign_logic(credit_transaction)
        assert amount == Decimal('1304.91')  # Flipped from negative to positive
        assert trans_type == 'CREDIT'
    
    def test_settlement_detection(self):
        """Test detection of settlement transactions."""
        from src.creditcard_mt940.parsers.ics_parser import RawTransaction
        from datetime import datetime
        from decimal import Decimal
        
        # Test settlement transaction
        settlement_transaction = RawTransaction(
            transaction_date=datetime(2025, 6, 28),
            booking_date=datetime(2025, 6, 28),
            description='GEINCASSEERD VORIG SALDO',
            cardholder_name='Test User',
            card_number='****null',
            debit_credit='C',
            amount=Decimal('-1304.91')
        )
        
        assert self.parser._is_previous_statement_settlement(settlement_transaction) is True
        
        # Test regular transaction
        regular_transaction = RawTransaction(
            transaction_date=datetime(2025, 6, 30),
            booking_date=datetime(2025, 7, 1),
            description='UPWORK TRANSACTION',
            cardholder_name='Test User',
            card_number='****4073',
            debit_credit='D',
            amount=Decimal('121.00')
        )
        
        assert self.parser._is_previous_statement_settlement(regular_transaction) is False
    
    def test_get_account_info(self, tmp_path):
        """Test extracting account information."""
        csv_content = """Transactiedatum;Boekingsdatum;Omschrijving;Naam Card-houder;Card nummer;Debit/Credit;Bedrag;Merchant categorie;Land;Valuta;Bedrag in oorspronkelijke valuta;Type transactie;WalletProvider
30-06-2025;01-07-2025;UPWORK -822746539REF DUBLIN IRL;"Crombag, DMP";****4073;D;121,00;Employment Agencies;IRL;EUR;121,00;Transaction;null
23-06-2025;24-06-2025;ADOBE  *ADOBE 044-207-3650 IRL;"Crombag, DMP";****4073;D;55,84;null;IRL;EUR;55,84;Transaction;null"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        account_info = self.parser.get_account_info(str(csv_file))
        
        assert 'NL00ICS0' in account_info['account_number']
        assert '0004073' in account_info['account_number']  # Card number with * replaced by 0
        assert account_info['start_date'] == datetime(2025, 6, 23)
        assert account_info['end_date'] == datetime(2025, 6, 30)
    
    def test_parse_with_foreign_currency(self, tmp_path):
        """Test parsing with foreign currency transactions."""
        csv_content = """Transactiedatum;Boekingsdatum;Omschrijving;Naam Card-houder;Card nummer;Debit/Credit;Bedrag;Merchant categorie;Land;Valuta;Bedrag in oorspronkelijke valuta;Type transactie;WalletProvider
14-06-2025;15-06-2025;FLYCART-DISCOUNT RULES SINGAPORE SGP;"Crombag, DMP";****4073;D;70,48;null;SGP;USD;79,00;Transaction;null
13-06-2025;14-06-2025;TRELLO.COM* ATLASSIAN NEW YORK USA;"Crombag, DMP";****4073;D;11,16;null;USA;USD;12,50;Transaction;null"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        
        # Both should be negative (Debit transactions)
        assert transactions[0].amount == Decimal('-70.48')
        assert transactions[0].description == 'FLYCART-DISCOUNT RULES SINGAPORE SGP'
        
        assert transactions[1].amount == Decimal('-11.16')
        assert transactions[1].description == 'TRELLO.COM* ATLASSIAN NEW YORK USA'
    
    def test_parse_date_formats(self):
        """Test parsing DD-MM-YYYY date format."""
        from src.creditcard_mt940.parsers.ics_parser import RawTransaction
        import pandas as pd
        
        # Create test data with DD-MM-YYYY format
        row_data = {
            'Transactiedatum': '30-06-2025',
            'Boekingsdatum': '01-07-2025',
            'Omschrijving': 'Test transaction',
            'Naam Card-houder': 'Test User',
            'Card nummer': '****4073',
            'Debit/Credit': 'D',
            'Bedrag': '121,00',
            'Valuta': 'EUR'
        }
        
        df = pd.DataFrame([row_data])
        transactions = self.parser._parse_raw_transactions(df)
        
        assert len(transactions) == 1
        assert transactions[0].transaction_date == datetime(2025, 6, 30)
        assert transactions[0].booking_date == datetime(2025, 7, 1)
    
    def test_european_amount_format(self):
        """Test parsing European amount format (comma as decimal separator)."""
        from src.creditcard_mt940.parsers.ics_parser import RawTransaction
        import pandas as pd
        
        # Test with comma decimal separator
        row_data = {
            'Transactiedatum': '30-06-2025',
            'Boekingsdatum': '01-07-2025',
            'Omschrijving': 'Test transaction',
            'Naam Card-houder': 'Test User',
            'Card nummer': '****4073',
            'Debit/Credit': 'D',
            'Bedrag': '1.234,56',  # European format
            'Valuta': 'EUR'
        }
        
        df = pd.DataFrame([row_data])
        transactions = self.parser._parse_raw_transactions(df)
        
        assert len(transactions) == 1
        assert transactions[0].amount == Decimal('1234.56')
    
    def test_counter_account_generation(self, tmp_path):
        """Test counter account generation from card number."""
        csv_content = """Transactiedatum;Boekingsdatum;Omschrijving;Naam Card-houder;Card nummer;Debit/Credit;Bedrag;Merchant categorie;Land;Valuta;Bedrag in oorspronkelijke valuta;Type transactie;WalletProvider
30-06-2025;01-07-2025;UPWORK TRANSACTION;"Crombag, DMP";****4073;D;121,00;Employment Agencies;IRL;EUR;121,00;Transaction;null"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 1
        # Counter account should be formatted as NL00ICS0 + card number with * replaced by 0
        assert transactions[0].counter_account == 'NL00ICS000004073'
    
    def test_reference_generation(self, tmp_path):
        """Test reference ID generation."""
        csv_content = """Transactiedatum;Boekingsdatum;Omschrijving;Naam Card-houder;Card nummer;Debit/Credit;Bedrag;Merchant categorie;Land;Valuta;Bedrag in oorspronkelijke valuta;Type transactie;WalletProvider
30-06-2025;01-07-2025;UPWORK TRANSACTION;"Crombag, DMP";****4073;D;121,00;Employment Agencies;IRL;EUR;121,00;Transaction;null
23-06-2025;24-06-2025;ADOBE TRANSACTION;"Crombag, DMP";****4073;D;55,84;null;IRL;EUR;55,84;Transaction;null"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        # References should start from 50000000001 for ICS
        assert transactions[0].reference == '50000000001'
        assert transactions[1].reference == '50000000002'