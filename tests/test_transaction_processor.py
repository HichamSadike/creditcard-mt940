"""Tests for transaction processor."""

import pytest
import tempfile
import os
from datetime import datetime
from decimal import Decimal

from src.creditcard_mt940.processors.transaction_processor import TransactionProcessor


class TestTransactionProcessor:
    """Test cases for TransactionProcessor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = TransactionProcessor()
        
        # Create sample CSV data
        self.sample_csv_data = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000008;1-3-2025;-19,3;GTRANSLATE.COM           GTRANSLATE.COUSAFL;19,99;USD;1,03575
NL54RABO0310737710;49000000009;1-3-2025;-0,39;Koersopslag;;;
NL54RABO0310737710;50000000005;26-3-2025;912,4;Verrekening vorig overzicht;;;
NL54RABO0310737710;50000000013;27-3-2025;-108;COOKIEBOT                KOEBENHAVN K DNK;;;"""
    
    def create_temp_csv(self, content):
        """Create a temporary CSV file with given content."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    
    def test_process_csv_to_mt940(self):
        """Test complete CSV to MT940 conversion."""
        temp_file = self.create_temp_csv(self.sample_csv_data)
        
        try:
            mt940_content = self.processor.process_csv_to_mt940(temp_file)
            
            # Check MT940 structure
            assert ":20:" in mt940_content  # Transaction reference
            assert ":25:" in mt940_content  # Account identification
            assert ":28C:" in mt940_content  # Statement number
            assert ":60F:" in mt940_content  # Opening balance
            assert ":61:" in mt940_content  # Transaction details
            assert ":86:" in mt940_content  # Transaction information
            assert ":62F:" in mt940_content  # Closing balance
            
            # Check account number
            assert "NL54RABO0310737710" in mt940_content
            
            # Check transaction descriptions
            assert "GTRANSLATE.COM" in mt940_content
            assert "SETTLEMENT PREVIOUS STATE" in mt940_content
            assert "COOKIEBOT" in mt940_content
            
        finally:
            os.unlink(temp_file)
    
    def test_process_csv_to_mt940_with_custom_params(self):
        """Test CSV to MT940 conversion with custom parameters."""
        temp_file = self.create_temp_csv(self.sample_csv_data)
        
        try:
            mt940_content = self.processor.process_csv_to_mt940(
                temp_file,
                account_number="NL99TEST0123456789",
                statement_number="CUSTOM001",
                opening_balance=Decimal('100.00')
            )
            
            # Check custom parameters
            assert "NL99TEST0123456789" in mt940_content
            assert "CUSTOM001" in mt940_content
            assert ":60F:C" in mt940_content  # Opening balance should be credit
            
        finally:
            os.unlink(temp_file)
    
    def test_get_transaction_summary(self):
        """Test transaction summary generation."""
        temp_file = self.create_temp_csv(self.sample_csv_data)
        
        try:
            summary = self.processor.get_transaction_summary(temp_file)
            
            # Check summary structure
            assert 'account_number' in summary
            assert 'date_range' in summary
            assert 'transaction_count' in summary
            assert 'total_credits' in summary
            assert 'total_debits' in summary
            assert 'net_total' in summary
            assert 'transactions' in summary
            
            # Check values
            assert summary['account_number'] == "NL54RABO0310737710"
            assert summary['transaction_count'] == 3
            assert summary['total_credits'] == Decimal('912.4')
            assert summary['total_debits'] == Decimal('-127.69')
            assert summary['net_total'] == Decimal('784.71')
            
            # Check date range
            assert summary['date_range']['start'] == datetime(2025, 3, 1)
            assert summary['date_range']['end'] == datetime(2025, 3, 27)
            
        finally:
            os.unlink(temp_file)
    
    def test_validate_csv_format_valid(self):
        """Test CSV format validation with valid file."""
        temp_file = self.create_temp_csv(self.sample_csv_data)
        
        try:
            validation_result = self.processor.validate_csv_format(temp_file)
            
            assert validation_result['valid'] is True
            assert 'message' in validation_result
            assert validation_result['row_count'] == 4
            
        finally:
            os.unlink(temp_file)
    
    def test_validate_csv_format_missing_columns(self):
        """Test CSV format validation with missing columns."""
        invalid_csv = """Tegenrekening IBAN;Datum;Bedrag;Omschrijving
NL54RABO0310737710;1-3-2025;-19,3;GTRANSLATE.COM"""
        
        temp_file = self.create_temp_csv(invalid_csv)
        
        try:
            validation_result = self.processor.validate_csv_format(temp_file)
            
            assert validation_result['valid'] is False
            assert 'Transactiereferentie' in validation_result['error']
            
        finally:
            os.unlink(temp_file)
    
    def test_validate_csv_format_empty_file(self):
        """Test CSV format validation with empty file."""
        empty_csv = "Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers\n"
        temp_file = self.create_temp_csv(empty_csv)
        
        try:
            validation_result = self.processor.validate_csv_format(temp_file)
            
            assert validation_result['valid'] is False
            assert "empty" in validation_result['error']
            
        finally:
            os.unlink(temp_file)
    
    def test_validate_csv_format_invalid_data(self):
        """Test CSV format validation with invalid data."""
        invalid_csv = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000008;invalid-date;invalid-amount;GTRANSLATE.COM;;;"""
        
        temp_file = self.create_temp_csv(invalid_csv)
        
        try:
            validation_result = self.processor.validate_csv_format(temp_file)
            
            assert validation_result['valid'] is False
            assert "Format validation errors" in validation_result['error']
            
        finally:
            os.unlink(temp_file)
    
    def test_generate_statement_number(self):
        """Test statement number generation."""
        test_date = datetime(2025, 3, 15)
        statement_number = self.processor._generate_statement_number(test_date)
        
        assert statement_number == "CC20250315"
    
    def test_calculate_opening_balance(self):
        """Test opening balance calculation."""
        # For credit card statements, opening balance should be 0
        opening_balance = self.processor._calculate_opening_balance([])
        assert opening_balance == Decimal('0.00')
    
    def test_nonexistent_file(self):
        """Test handling of non-existent files."""
        validation_result = self.processor.validate_csv_format("nonexistent_file.csv")
        
        assert validation_result['valid'] is False
        assert "Error reading CSV file" in validation_result['error']
    
    def test_malformed_csv(self):
        """Test handling of malformed CSV files."""
        malformed_csv = "This is not a valid CSV file"
        temp_file = self.create_temp_csv(malformed_csv)
        
        try:
            validation_result = self.processor.validate_csv_format(temp_file)
            
            assert validation_result['valid'] is False
            assert "Missing required columns" in validation_result['error']
            
        finally:
            os.unlink(temp_file)