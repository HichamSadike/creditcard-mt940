"""Tests for Rabobank parser."""

import pytest
from decimal import Decimal
from datetime import datetime
from src.creditcard_mt940.parsers.rabobank_old_parser import RabobankParser
from src.creditcard_mt940.mt940.formatter import Transaction


class TestRabobankParser:
    """Test cases for RabobankParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = RabobankParser()
    
    def test_get_bank_name(self):
        """Test bank name."""
        assert self.parser.get_bank_name() == 'Rabobank'
    
    def test_get_supported_file_types(self):
        """Test supported file types."""
        assert self.parser.get_supported_file_types() == ['csv']
    
    def test_validate_file_format_valid(self, tmp_path):
        """Test validation with valid CSV."""
        csv_content = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000007;27-2-2025;-108;COOKIEBOT B.V.;;EUR;
NL54RABO0310737710;49000000008;28-2-2025;-15.50;STORE PURCHASE;;EUR;"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is True
        assert 'Rabobank' in result['message']
    
    def test_validate_file_format_invalid_separator(self, tmp_path):
        """Test validation with invalid separator."""
        csv_content = """Tegenrekening IBAN,Transactiereferentie,Datum,Bedrag,Omschrijving
NL54RABO0310737710,49000000007,27-2-2025,-108,COOKIEBOT B.V."""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is False
    
    def test_validate_file_format_missing_columns(self, tmp_path):
        """Test validation with missing required columns."""
        csv_content = """Datum;Bedrag;Omschrijving
27-2-2025;-108;COOKIEBOT B.V."""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is False
        assert 'Missing required columns' in result['error']
    
    def test_parse_file_basic(self, tmp_path):
        """Test basic file parsing."""
        csv_content = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000007;27-2-2025;-108;COOKIEBOT B.V.;;EUR;
NL54RABO0310737710;49000000008;28-2-2025;-15.50;STORE PURCHASE;;EUR;"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        assert transactions[0].amount == Decimal('-108.00')
        assert transactions[0].description == 'COOKIEBOT B.V.'
        assert transactions[0].reference == '49000000007'
        assert transactions[0].date == datetime(2025, 2, 27)
        assert transactions[0].counter_account == 'NL54RABO0310737710'
    
    def test_parse_file_with_surcharge_merging(self, tmp_path):
        """Test parsing with exchange rate surcharge merging."""
        csv_content = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000007;27-2-2025;-108;COOKIEBOT B.V.;;EUR;
NL54RABO0310737710;49000000008;27-2-2025;-2.50;Koersopslag;;EUR;
NL54RABO0310737710;49000000009;28-2-2025;-15.50;STORE PURCHASE;;EUR;"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        # Should have 2 transactions - surcharge merged with first transaction
        assert len(transactions) == 2
        assert transactions[0].amount == Decimal('-110.50')  # -108 + -2.50
        assert 'COOKIEBOT B.V.' in transactions[0].description
        assert transactions[1].amount == Decimal('-15.50')
        assert transactions[1].description == 'STORE PURCHASE'
    
    def test_parse_file_with_settlement(self, tmp_path):
        """Test parsing with previous statement settlement."""
        csv_content = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000007;27-2-2025;-108;COOKIEBOT B.V.;;EUR;
NL54RABO0310737710;49000000008;28-2-2025;-150.00;Verrekening vorig overzicht;;EUR;"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        
        assert len(transactions) == 2
        assert transactions[0].amount == Decimal('-108.00')
        assert transactions[1].amount == Decimal('150.00')  # Converted to positive
        assert transactions[1].description == 'Settlement previous statement'
    
    def test_get_account_info(self, tmp_path):
        """Test extracting account information."""
        csv_content = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000007;27-2-2025;-108;COOKIEBOT B.V.;;EUR;
NL54RABO0310737710;49000000008;28-2-2025;-15.50;STORE PURCHASE;;EUR;"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        account_info = self.parser.get_account_info(str(csv_file))
        
        assert account_info['account_number'] == 'NL54RABO0310737710'
        assert account_info['start_date'] == datetime(2025, 2, 27)
        assert account_info['end_date'] == datetime(2025, 2, 28)
    
    def test_calculate_totals(self, tmp_path):
        """Test calculating transaction totals."""
        csv_content = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000007;27-2-2025;-108;COOKIEBOT B.V.;;EUR;
NL54RABO0310737710;49000000008;28-2-2025;-15.50;STORE PURCHASE;;EUR;
NL54RABO0310737710;49000000009;28-2-2025;-150.00;Verrekening vorig overzicht;;EUR;"""
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding='utf-8')
        
        transactions = self.parser.parse_file(str(csv_file))
        totals = self.parser.calculate_totals(transactions)
        
        assert totals['transaction_count'] == 3
        assert totals['total_credits'] == Decimal('150.00')  # Settlement converted to positive
        assert totals['total_debits'] == Decimal('-123.50')  # -108 + -15.50
        assert totals['net_total'] == Decimal('26.50')
    
