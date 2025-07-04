"""Base parser interface for different bank CSV/Excel formats."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional
from ..mt940.formatter import Transaction


class BaseParser(ABC):
    """Abstract base class for bank-specific parsers."""
    
    def __init__(self):
        self.bank_name = self.get_bank_name()
        self.supported_file_types = self.get_supported_file_types()
    
    @abstractmethod
    def get_bank_name(self) -> str:
        """Return the name of the bank this parser handles."""
        pass
    
    @abstractmethod
    def get_supported_file_types(self) -> List[str]:
        """Return list of supported file extensions (e.g., ['csv', 'xlsx'])."""
        pass
    
    @abstractmethod
    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse bank-specific file and return list of transactions."""
        pass
    
    @abstractmethod
    def get_account_info(self, file_path: str) -> Dict:
        """Extract account information from file."""
        pass
    
    @abstractmethod
    def validate_file_format(self, file_path: str) -> Dict:
        """Validate file format and return validation results."""
        pass
    
    def calculate_totals(self, transactions: List[Transaction]) -> Dict:
        """Calculate transaction totals (common across all banks)."""
        total_credits = sum(t.amount for t in transactions if t.amount > 0)
        total_debits = sum(t.amount for t in transactions if t.amount < 0)
        net_total = total_credits + total_debits
        
        return {
            'total_credits': total_credits,
            'total_debits': total_debits,
            'net_total': net_total,
            'transaction_count': len(transactions)
        }