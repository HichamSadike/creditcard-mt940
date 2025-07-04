"""Tests for AMEX parser."""

import pytest
from decimal import Decimal
from datetime import datetime
from src.creditcard_mt940.parsers.amex_parser import AmexParser
from src.creditcard_mt940.mt940.formatter import Transaction
import pandas as pd


class TestAmexParser:
    """Test cases for AmexParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = AmexParser()
    
    def test_get_bank_name(self):
        """Test bank name."""
        assert self.parser.get_bank_name() == 'AMEX'
    
    def test_get_supported_file_types(self):
        """Test supported file types."""
        assert self.parser.get_supported_file_types() == ['xlsx', 'xls']
    
    def test_validate_file_format_valid(self, tmp_path):
        """Test validation with valid Excel file."""
        # Create test Excel file
        data = {
            'Date': ['2025-05-05', '2025-05-06'],
            'Amount': ['-100.50', '-25.00'],
            'Description': ['Store Purchase', 'Restaurant']
        }
        df = pd.DataFrame(data)
        
        excel_file = tmp_path / "test.xlsx"
        df.to_excel(excel_file, index=False)
        
        result = self.parser.validate_file_format(str(excel_file))
        assert result['valid'] is True
        assert 'AMEX' in result['message']
    
    def test_validate_file_format_invalid_extension(self, tmp_path):
        """Test validation with invalid file extension."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("dummy content", encoding='utf-8')
        
        result = self.parser.validate_file_format(str(csv_file))
        assert result['valid'] is False
        assert 'Excel' in result['error']
    
    def test_validate_file_format_empty_file(self, tmp_path):
        """Test validation with empty Excel file."""
        df = pd.DataFrame()
        
        excel_file = tmp_path / "test.xlsx"
        df.to_excel(excel_file, index=False)
        
        result = self.parser.validate_file_format(str(excel_file))
        assert result['valid'] is False
        assert 'empty' in result['error']
    
    def test_parse_file_basic(self, tmp_path):
        """Test basic file parsing with proper column structure."""
        # Create DataFrame with Date in column 0, another column, Amount in column 2, Description in column 3
        data = {
            'Date': ['2025-05-05', '2025-05-06'],
            'Reference': ['REF001', 'REF002'],
            'Bedrag': ['-100.50', '-25.00'],  # Amount in column 3 (index 2)
            'Description': ['Store Purchase', 'Restaurant']
        }
        df = pd.DataFrame(data)
        
        excel_file = tmp_path / "test.xlsx"
        df.to_excel(excel_file, index=False)
        
        transactions = self.parser.parse_file(str(excel_file))
        
        assert len(transactions) == 2
        assert transactions[0].amount == Decimal('-100.50')
        assert transactions[0].description == 'Store Purchase'
        assert transactions[0].date == datetime(2025, 5, 5)
        assert transactions[0].counter_account == 'NL00AMEX0000000000'
        assert transactions[0].reference == '49000000001'
        assert transactions[0].transaction_type == 'TRANSFER'
        
        assert transactions[1].amount == Decimal('-25.00')
        assert transactions[1].description == 'Restaurant'
        assert transactions[1].date == datetime(2025, 5, 6)
        assert transactions[1].reference == '49000000002'
    
    def test_parse_file_with_payments(self, tmp_path):
        """Test parsing with payment transactions."""
        data = {
            'Date': ['2025-05-05', '2025-05-06', '2025-05-07'],
            'Reference': ['REF001', 'REF002', 'REF003'],
            'Bedrag': ['-100.50', '-250.00', '-25.00'],  # Amount in column 3 (index 2)
            'Description': ['Store Purchase', 'HARTELIJK BEDANKT VOOR UW BETALING', 'Restaurant']
        }
        df = pd.DataFrame(data)
        
        excel_file = tmp_path / "test.xlsx"
        df.to_excel(excel_file, index=False)
        
        transactions = self.parser.parse_file(str(excel_file))
        
        assert len(transactions) == 3
        assert transactions[0].amount == Decimal('-100.50')
        assert transactions[0].transaction_type == 'TRANSFER'
        
        # Payment should be positive
        assert transactions[1].amount == Decimal('250.00')
        assert transactions[1].description == 'HARTELIJK BEDANKT VOOR UW BETALING'
        assert transactions[1].transaction_type == 'CREDIT'
        
        assert transactions[2].amount == Decimal('-25.00')
        assert transactions[2].transaction_type == 'TRANSFER'
    
    def test_parse_file_with_different_payment_keywords(self, tmp_path):
        """Test parsing with different payment keywords."""
        data = {
            'Date': ['2025-05-05', '2025-05-06', '2025-05-07', '2025-05-08'],
            'Reference': ['REF001', 'REF002', 'REF003', 'REF004'],
            'Bedrag': ['-100.50', '-250.00', '-300.00', '-25.00'],  # Amount in column 3 (index 2)
            'Description': [
                'Store Purchase', 
                'hartelijk bedankt voor uw betaling',  # lowercase
                'DANK U VOOR UW BETALING',  # different phrase - should NOT be detected as payment
                'Restaurant'
            ]
        }
        df = pd.DataFrame(data)
        
        excel_file = tmp_path / "test.xlsx"
        df.to_excel(excel_file, index=False)
        
        transactions = self.parser.parse_file(str(excel_file))
        
        assert len(transactions) == 4
        assert transactions[0].amount == Decimal('-100.50')
        assert transactions[0].transaction_type == 'TRANSFER'
        
        # Only "hartelijk bedankt voor uw betaling" should be detected as payment
        assert transactions[1].amount == Decimal('250.00')
        assert transactions[1].transaction_type == 'CREDIT'
        
        # "DANK U VOOR UW BETALING" is NOT in payment_keywords, should remain negative
        assert transactions[2].amount == Decimal('-300.00')
        assert transactions[2].transaction_type == 'TRANSFER'
        
        assert transactions[3].amount == Decimal('-25.00')
        assert transactions[3].transaction_type == 'TRANSFER'
    
    def test_parse_file_with_header_detection(self, tmp_path):
        """Test parsing with header detection in Excel file."""
        # Create Excel file with some empty rows and metadata
        data = {
            'Account Statement': ['', '', ''],
            'Unnamed: 1': ['', '', ''],
            'Unnamed: 2': ['', '', '']
        }
        metadata_df = pd.DataFrame(data)
        
        transaction_data = {
            'Date': ['2025-05-05', '2025-05-06'],
            'Amount': ['-100.50', '-25.00'],
            'Description': ['Store Purchase', 'Restaurant']
        }
        transaction_df = pd.DataFrame(transaction_data)
        
        # Combine dataframes
        combined_df = pd.concat([metadata_df, transaction_df], ignore_index=True)
        
        excel_file = tmp_path / "test.xlsx"
        combined_df.to_excel(excel_file, index=False)
        
        transactions = self.parser.parse_file(str(excel_file))
        
        assert len(transactions) == 2
        assert transactions[0].description == 'Store Purchase'
        assert transactions[1].description == 'Restaurant'
    
    def test_get_account_info(self, tmp_path):
        """Test extracting account information."""
        data = {
            'Date': ['2025-05-05', '2025-05-06'],
            'Amount': ['-100.50', '-25.00'],
            'Description': ['Store Purchase', 'Restaurant']
        }
        df = pd.DataFrame(data)
        
        excel_file = tmp_path / "test.xlsx"
        df.to_excel(excel_file, index=False)
        
        account_info = self.parser.get_account_info(str(excel_file))
        
        assert account_info['account_number'] == 'NL00AMEX0000000000'
        assert account_info['start_date'] == datetime(2025, 5, 5)
        assert account_info['end_date'] == datetime(2025, 5, 6)
    
    def test_calculate_totals(self, tmp_path):
        """Test calculating transaction totals."""
        data = {
            'Date': ['2025-05-05', '2025-05-06', '2025-05-07'],
            'Amount': ['-100.50', '-250.00', '-25.00'],
            'Description': ['Store Purchase', 'HARTELIJK BEDANKT VOOR UW BETALING', 'Restaurant']
        }
        df = pd.DataFrame(data)
        
        excel_file = tmp_path / "test.xlsx"
        df.to_excel(excel_file, index=False)
        
        transactions = self.parser.parse_file(str(excel_file))
        totals = self.parser.calculate_totals(transactions)
        
        assert totals['transaction_count'] == 3
        assert totals['total_credits'] == Decimal('250.00')  # Payment converted to positive
        assert totals['total_debits'] == Decimal('-125.50')  # -100.50 + -25.00
        assert totals['net_total'] == Decimal('124.50')
    
    def test_apply_amex_logic(self):
        """Test AMEX-specific transaction logic."""
        # Test payment transaction
        amount1, type1 = self.parser._apply_amex_logic(Decimal('-250.00'), 'HARTELIJK BEDANKT VOOR UW BETALING')
        assert amount1 == Decimal('250.00')
        assert type1 == 'CREDIT'
        
        # Test regular transaction
        amount2, type2 = self.parser._apply_amex_logic(Decimal('-100.50'), 'Store Purchase')
        assert amount2 == Decimal('-100.50')
        assert type2 == 'TRANSFER'  # Changed from CARD to TRANSFER for Rabobank compatibility
        
        # Test case insensitive
        amount3, type3 = self.parser._apply_amex_logic(Decimal('-300.00'), 'hartelijk bedankt voor uw betaling')
        assert amount3 == Decimal('300.00')
        assert type3 == 'CREDIT'
    
    def test_find_data_start_row(self):
        """Test finding the start row of transaction data."""
        # Test DataFrame with header row
        data = {
            'Date': ['2025-05-05', '2025-05-06'],
            'Amount': ['-100.50', '-25.00'],
            'Description': ['Store Purchase', 'Restaurant']
        }
        df = pd.DataFrame(data)
        
        start_row = self.parser._find_data_start_row(df)
        assert start_row == 0  # Data starts immediately
        
        # Test DataFrame with metadata rows
        metadata = {
            'Col1': ['Account Statement', '', 'Date'],
            'Col2': ['', '', 'Amount'],
            'Col3': ['', '', 'Description']
        }
        df_with_metadata = pd.DataFrame(metadata)
        
        start_row = self.parser._find_data_start_row(df_with_metadata)
        assert start_row == 2  # Data starts at row 2
    
    def test_parse_date_formats(self):
        """Test parsing various date formats."""
        # Test different date formats
        date1 = self.parser._parse_date('2025-05-05')
        assert date1 == datetime(2025, 5, 5)
        
        date2 = self.parser._parse_date('05/05/2025')
        assert date2 == datetime(2025, 5, 5)
        
        date3 = self.parser._parse_date('05-05-2025')
        assert date3 == datetime(2025, 5, 5)
        
        # Test pandas timestamp
        import pandas as pd
        timestamp = pd.Timestamp('2025-05-05')
        date4 = self.parser._parse_date(timestamp)
        assert date4 == datetime(2025, 5, 5)
    
    def test_clean_amount_formats(self):
        """Test cleaning various amount formats."""
        assert self.parser._clean_amount('-100.50') == Decimal('-100.50')
        assert self.parser._clean_amount('50.00') == Decimal('50.00')
        assert self.parser._clean_amount('-25,50') == Decimal('-25.50')
        assert self.parser._clean_amount('€ 100.50') == Decimal('100.50')
        assert self.parser._clean_amount('$ -75.25') == Decimal('-75.25')
        
        # Test invalid amount
        with pytest.raises(ValueError):
            self.parser._clean_amount('invalid')
    
    def test_generate_reference_id(self):
        """Test reference ID generation."""
        ref1 = self.parser._generate_reference_id(datetime(2025, 5, 5), 1)
        assert ref1 == '49000000001'
        
        ref2 = self.parser._generate_reference_id(datetime(2024, 12, 31), 999)
        assert ref2 == '49000000999'
    
    def test_parse_empty_file(self, tmp_path):
        """Test parsing empty Excel file."""
        df = pd.DataFrame()
        
        excel_file = tmp_path / "test.xlsx"
        df.to_excel(excel_file, index=False)
        
        with pytest.raises(ValueError):
            self.parser.parse_file(str(excel_file))
    
    def test_parse_file_with_missing_columns(self, tmp_path):
        """Test parsing file with missing required columns."""
        data = {
            'Date': ['2025-05-05', '2025-05-06'],
            'Description': ['Store Purchase', 'Restaurant']
            # Missing Amount column
        }
        df = pd.DataFrame(data)
        
        excel_file = tmp_path / "test.xlsx"
        df.to_excel(excel_file, index=False)
        
        with pytest.raises(ValueError):
            self.parser.parse_file(str(excel_file))