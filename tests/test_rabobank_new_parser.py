"""Tests for new Rabobank parser."""

import pytest
from decimal import Decimal
from datetime import datetime
from src.creditcard_mt940.parsers.rabobank_new_parser import RabobankNewParser
from src.creditcard_mt940.mt940.formatter import Transaction


class TestRabobankNewParser:
    """Test cases for RabobankNewParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = RabobankNewParser()
    
    def test_get_bank_name(self):
        """Test bank name."""
        assert self.parser.get_bank_name() == 'Rabobank'
    
    def test_get_supported_file_types(self):
        """Test supported file types."""
        assert self.parser.get_supported_file_types() == ['csv']
    
    def test_validate_file_format_valid(self, tmp_path):
        """Test validation with valid CSV."""
        csv_content = """Counterpty IBAN,Ccy,Credit Card Number,Product Name,Credit Card Line1,Credit Card Line2,Transaction Reference,Date,Amount,Description,Instr Amt,Instr Ccy,Rate
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0002000000001,2025-06-02,-2.88,APPLE.COM/BILL           ITUNES.COM   IRL   Apple Pay,,,
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0002000000002,2025-06-05,-141.95,A-Mac Maastricht         Maastricht   NLD   Apple Pay,,,"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is True
        assert 'New format Rabobank' in result['message']
    
    def test_validate_file_format_missing_columns(self, tmp_path):
        """Test validation with missing required columns."""
        csv_content = """Date,Amount,Description
2025-06-02,-2.88,APPLE.COM/BILL"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is False
        assert 'Missing required columns' in result['error']
    
    def test_parse_file_basic(self, tmp_path):
        """Test basic file parsing."""
        csv_content = """Counterpty IBAN,Ccy,Credit Card Number,Product Name,Credit Card Line1,Credit Card Line2,Transaction Reference,Date,Amount,Description,Instr Amt,Instr Ccy,Rate
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0002000000001,2025-06-02,-2.88,APPLE.COM/BILL           ITUNES.COM   IRL   Apple Pay,,,
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0002000000002,2025-06-05,-141.95,A-Mac Maastricht         Maastricht   NLD   Apple Pay,,,"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        assert transactions[0].amount == Decimal('-2.88')
        assert transactions[0].description == 'APPLE.COM/BILL           ITUNES.COM   IRL   Apple Pay'
        assert transactions[0].reference == '2000000001'
        assert transactions[0].date == datetime(2025, 6, 2)
        assert transactions[0].counter_account == 'NL92RABO0001234567'
    
    def test_parse_file_with_foreign_currency(self, tmp_path):
        """Test parsing with foreign currency transactions."""
        csv_content = """Counterpty IBAN,Ccy,Credit Card Number,Product Name,Credit Card Line1,Credit Card Line2,Transaction Reference,Date,Amount,Description,Instr Amt,Instr Ccy,Rate
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0002000000004,2025-06-10,-5.60,KARAVANSTOP              CHEK LAP KOK HKG   Apple Pay,50.00,HKD,8.92857
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0002000000005,2025-06-10,-0.11,Koersopslag,,,"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        # Should combine the transaction with koersopslag
        assert len(transactions) == 1
        assert transactions[0].amount == Decimal('-5.71')  # -5.60 + -0.11
        assert 'exchange rate surcharge' in transactions[0].description
    
    def test_parse_file_with_settlement(self, tmp_path):
        """Test parsing with previous statement settlement."""
        csv_content = """Counterpty IBAN,Ccy,Credit Card Number,Product Name,Credit Card Line1,Credit Card Line2,Transaction Reference,Date,Amount,Description,Instr Amt,Instr Ccy,Rate
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0002000000001,2025-06-02,-2.88,APPLE.COM/BILL           ITUNES.COM   IRL   Apple Pay,,,
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0003000000021,2025-06-25,+593.23,Verrekening vorig overzicht,,,"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        assert transactions[0].amount == Decimal('-2.88')
        assert transactions[1].amount == Decimal('593.23')  # Settlement should be positive
        assert transactions[1].transaction_type == 'CREDIT'
    
    def test_get_account_info(self, tmp_path):
        """Test extracting account information."""
        csv_content = """Counterpty IBAN,Ccy,Credit Card Number,Product Name,Credit Card Line1,Credit Card Line2,Transaction Reference,Date,Amount,Description,Instr Amt,Instr Ccy,Rate
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0002000000001,2025-06-02,-2.88,APPLE.COM/BILL           ITUNES.COM   IRL   Apple Pay,,,
NL58RABO0364024879,EUR,4204,Rabo BusinessCard Visa,M. CHOJNACKA,ICTM CONSULTING,0002000000002,2025-06-05,-141.95,A-Mac Maastricht         Maastricht   NLD   Apple Pay,,,"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        account_info = self.parser.get_account_info(str(csv_file))

        assert account_info['account_number'] == 'NL92RABO0001234567'
        assert account_info['start_date'] == datetime(2025, 6, 2)
        assert account_info['end_date'] == datetime(2025, 6, 5)
    
    def test_parse_date_iso_format(self):
        """Test parsing ISO date format (YYYY-MM-DD)."""
        from src.creditcard_mt940.parsers.rabobank_new_parser import RawTransaction
        
        # Create a mock row to test date parsing
        import pandas as pd
        row_data = {
            'Date': '2025-06-02',
            'Amount': '-2.88',
            'Description': 'Test transaction',
            'Counterpty IBAN': 'NL58RABO0364024879',
            'Transaction Reference': '0002000000001',
            'Ccy': 'EUR'
        }
        row = pd.Series(row_data)
        
        transaction = self.parser._parse_raw_transactions(pd.DataFrame([row_data]))[0]
        assert transaction.date == datetime(2025, 6, 2)
    
    def test_clean_amount_european_format(self):
        """Test cleaning European amount format (comma as decimal separator)."""
        from src.creditcard_mt940.parsers.rabobank_new_parser import RawTransaction
        
        # Test parsing amounts with comma decimal separator
        import pandas as pd
        row_data = {
            'Date': '2025-06-02',
            'Amount': '-2,88',  # European format with comma
            'Description': 'Test transaction',
            'Counterpty IBAN': 'NL58RABO0364024879',
            'Transaction Reference': '0002000000001',
            'Ccy': 'EUR'
        }
        
        transaction = self.parser._parse_raw_transactions(pd.DataFrame([row_data]))[0]
        assert transaction.amount == Decimal('-2.88')
    
    def test_exchange_rate_surcharge_detection(self):
        """Test detection of exchange rate surcharges."""
        from src.creditcard_mt940.parsers.rabobank_new_parser import RawTransaction
        from datetime import datetime
        from decimal import Decimal
        
        # Test koersopslag detection
        koersopslag_transaction = RawTransaction(
            counter_account='NL58RABO0364024879',
            reference='0002000000005',
            date=datetime(2025, 6, 10),
            amount=Decimal('-0.11'),
            description='Koersopslag'
        )
        
        assert self.parser._is_exchange_rate_surcharge(koersopslag_transaction) is True
        
        # Test normal transaction
        normal_transaction = RawTransaction(
            counter_account='NL58RABO0364024879',
            reference='0002000000004',
            date=datetime(2025, 6, 10),
            amount=Decimal('-5.60'),
            description='KARAVANSTOP              CHEK LAP KOK HKG   Apple Pay'
        )
        
        assert self.parser._is_exchange_rate_surcharge(normal_transaction) is False
    
    def test_transaction_classification(self):
        """Test transaction type classification."""
        from src.creditcard_mt940.parsers.rabobank_new_parser import RawTransaction
        from datetime import datetime
        from decimal import Decimal
        
        # Test Apple Pay transaction
        apple_pay_transaction = RawTransaction(
            counter_account='NL58RABO0364024879',
            reference='0002000000001',
            date=datetime(2025, 6, 2),
            amount=Decimal('-2.88'),
            description='APPLE.COM/BILL           ITUNES.COM   IRL   Apple Pay'
        )
        
        assert self.parser._classify_transaction(apple_pay_transaction) == 'CARD'
        
        # Test positive amount (credit)
        credit_transaction = RawTransaction(
            counter_account='NL58RABO0364024879',
            reference='0003000000021',
            date=datetime(2025, 6, 25),
            amount=Decimal('593.23'),
            description='Verrekening vorig overzicht'
        )
        
        assert self.parser._classify_transaction(credit_transaction) == 'CREDIT'
        
        # Test regular transaction
        regular_transaction = RawTransaction(
            counter_account='NL58RABO0364024879',
            reference='0002000000006',
            date=datetime(2025, 6, 10),
            amount=Decimal('-31.11'),
            description='UMS*ERKE                 SHAMENSHI    CHN'
        )
        
        assert self.parser._classify_transaction(regular_transaction) == 'TRANSFER'