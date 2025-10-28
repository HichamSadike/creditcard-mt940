"""Tests for ING parser."""

import pytest
from decimal import Decimal
from datetime import datetime
from src.creditcard_mt940.parsers.ing_parser import IngParser
from src.creditcard_mt940.mt940.formatter import Transaction


class TestIngParser:
    """Test cases for IngParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = IngParser()
    
    def test_get_bank_name(self):
        """Test bank name."""
        assert self.parser.get_bank_name() == 'ING'
    
    def test_get_supported_file_types(self):
        """Test supported file types."""
        assert self.parser.get_supported_file_types() == ['csv']
    
    def test_validate_file_format_valid(self, tmp_path):
        """Test validation with valid CSV."""
        csv_content = """"Accountnummer","Kaartnummer","Naam op kaart","Transactiedatum","Boekingsdatum","Omschrijving","Valuta","Bedrag","Koers","Bedrag in EUR"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-05","2025-05-05","Canva* 04506-56920230 Sydney AUS","","","","-11,99"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-06","2025-05-06","Store Purchase","","","","-25,50\""""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is True
        assert 'ING' in result['message']
    
    def test_validate_file_format_invalid_separator(self, tmp_path):
        """Test validation with invalid separator."""
        csv_content = """Accountnummer;Kaartnummer;Naam op kaart;Transactiedatum;Boekingsdatum;Omschrijving;Valuta;Bedrag;Koers;Bedrag in EUR
00000374942;5534.****.****.5722;K.Z. CHIARETTI;2025-05-05;2025-05-05;Canva* 04506-56920230 Sydney AUS;;;;;-11,99"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is False
        assert 'comma' in result['error']
    
    def test_validate_file_format_missing_columns(self, tmp_path):
        """Test validation with missing required columns."""
        csv_content = """"Transactiedatum","Omschrijving","Bedrag in EUR"
"2025-05-05","Canva* 04506-56920230 Sydney AUS","-11,99\""""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is False
        assert 'missing required columns' in result['error']
    
    def test_parse_file_basic(self, tmp_path):
        """Test basic file parsing."""
        csv_content = """"Accountnummer","Kaartnummer","Naam op kaart","Transactiedatum","Boekingsdatum","Omschrijving","Valuta","Bedrag","Koers","Bedrag in EUR"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-05","2025-05-05","Canva* 04506-56920230 Sydney AUS","","","","-11,99"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-06","2025-05-06","Store Purchase","","","","-25,50\""""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        assert transactions[0].amount == Decimal('-11.99')
        assert transactions[0].description == 'Canva* 04506-56920230 Sydney AUS'
        assert transactions[0].date == datetime(2025, 5, 5)
        assert transactions[0].counter_account == 'NL98INGB1234567890'
        assert transactions[0].reference == 'ING_000000'
        
        assert transactions[1].amount == Decimal('-25.50')
        assert transactions[1].description == 'Store Purchase'
        assert transactions[1].date == datetime(2025, 5, 6)
        assert transactions[1].reference == 'ING_000001'
    
    def test_parse_file_with_positive_amounts(self, tmp_path):
        """Test parsing with positive amounts (credits)."""
        csv_content = """"Accountnummer","Kaartnummer","Naam op kaart","Transactiedatum","Boekingsdatum","Omschrijving","Valuta","Bedrag","Koers","Bedrag in EUR"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-05","2025-05-05","Payment Refund","","","","50,00"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-06","2025-05-06","Store Purchase","","","","-25,50\""""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        assert transactions[0].amount == Decimal('50.00')
        assert transactions[0].description == 'Payment Refund'
        assert transactions[1].amount == Decimal('-25.50')
        assert transactions[1].description == 'Store Purchase'
    
    def test_get_account_info(self, tmp_path):
        """Test extracting account information."""
        csv_content = """"Accountnummer","Kaartnummer","Naam op kaart","Transactiedatum","Boekingsdatum","Omschrijving","Valuta","Bedrag","Koers","Bedrag in EUR"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-05","2025-05-05","Canva* 04506-56920230 Sydney AUS","","","","-11,99"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-06","2025-05-06","Store Purchase","","","","-25,50\""""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        account_info = self.parser.get_account_info(str(csv_file))

        assert account_info['account_number'] == 'NL98INGB1234567890'
        assert account_info['start_date'] == datetime(2025, 5, 5)
        assert account_info['end_date'] == datetime(2025, 5, 6)
    
    def test_calculate_totals(self, tmp_path):
        """Test calculating transaction totals."""
        csv_content = """"Accountnummer","Kaartnummer","Naam op kaart","Transactiedatum","Boekingsdatum","Omschrijving","Valuta","Bedrag","Koers","Bedrag in EUR"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-05","2025-05-05","Payment Refund","","","","50,00"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-06","2025-05-06","Store Purchase","","","","-25,50"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-07","2025-05-07","Another Purchase","","","","-30,00\""""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        totals = self.parser.calculate_totals(transactions)
        
        assert totals['transaction_count'] == 3
        assert totals['total_credits'] == Decimal('50.00')
        assert totals['total_debits'] == Decimal('-55.50')  # -25.50 + -30.00
        assert totals['net_total'] == Decimal('-5.50')
    
    def test_parse_date_formats(self):
        """Test parsing various date formats."""
        # Test YYYY-MM-DD format
        date1 = self.parser._parse_date('2025-05-05')
        assert date1 == datetime(2025, 5, 5)
        
        date2 = self.parser._parse_date('2024-12-01')
        assert date2 == datetime(2024, 12, 1)
        
        # Test invalid date
        with pytest.raises(ValueError):
            self.parser._parse_date('invalid-date')
    
    def test_clean_amount_formats(self):
        """Test cleaning various amount formats."""
        assert self.parser._clean_amount('-11,99') == Decimal('-11.99')
        assert self.parser._clean_amount('50,00') == Decimal('50.00')
        assert self.parser._clean_amount('-25.50') == Decimal('-25.50')
        assert self.parser._clean_amount('0') == Decimal('0.00')
        
        # Test invalid amount
        with pytest.raises(ValueError):
            self.parser._clean_amount('invalid')
    
    def test_generate_reference_id(self):
        """Test reference ID generation."""
        ref1 = self.parser._generate_reference_id(datetime(2025, 5, 5), 1)
        assert ref1 == 'ING-20250505-1'
        
        ref2 = self.parser._generate_reference_id(datetime(2024, 12, 31), 999)
        assert ref2 == 'ING-20241231-999'
    
    def test_parse_empty_file(self, tmp_path):
        """Test parsing empty file."""
        csv_content = """"Accountnummer","Kaartnummer","Naam op kaart","Transactiedatum","Boekingsdatum","Omschrijving","Valuta","Bedrag","Koers","Bedrag in EUR\""""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        assert len(transactions) == 0
    
    def test_parse_file_with_special_characters(self, tmp_path):
        """Test parsing file with special characters in descriptions."""
        csv_content = """"Accountnummer","Kaartnummer","Naam op kaart","Transactiedatum","Boekingsdatum","Omschrijving","Valuta","Bedrag","Koers","Bedrag in EUR"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-05","2025-05-05","Café & Restaurant München","","","","-11,99"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-06","2025-05-06","Store w/ \"Special\" Chars","","","","-25,50\""""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        assert transactions[0].description == 'Café & Restaurant München'
        assert transactions[1].description == 'Store w/ "Special" Chars'