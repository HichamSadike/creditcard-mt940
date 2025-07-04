"""CAMT.053 formatter for converting transactions to CAMT.053 XML format."""

from datetime import datetime
from decimal import Decimal
from typing import List
import xml.etree.ElementTree as ET
from xml.dom import minidom

from ..mt940.formatter import Transaction, AccountStatement


class CAMT053Formatter:
    """Formats transactions into CAMT.053 XML format."""
    
    def __init__(self):
        self.message_id_counter = 1
    
    def format_statement(self, statement: AccountStatement) -> str:
        """Format an account statement into CAMT.053 XML format."""
        # Create root element
        root = ET.Element("Document")
        root.set("xmlns", "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        
        # Bank to customer statement
        bk_to_cstmr_stmt = ET.SubElement(root, "BkToCstmrStmt")
        
        # Group header
        grp_hdr = ET.SubElement(bk_to_cstmr_stmt, "GrpHdr")
        
        msg_id = ET.SubElement(grp_hdr, "MsgId")
        msg_id.text = f"RABO{statement.statement_number}{datetime.now().strftime('%H%M%S')}"
        
        cre_dt_tm = ET.SubElement(grp_hdr, "CreDtTm")
        cre_dt_tm.text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        # Message recipient (optional but adds authenticity)
        msg_rcpt = ET.SubElement(grp_hdr, "MsgRcpt")
        msg_rcpt_nm = ET.SubElement(msg_rcpt, "Nm")
        msg_rcpt_nm.text = "Customer"
        
        # Initiating party (the bank)
        initg_pty = ET.SubElement(grp_hdr, "InitgPty")
        initg_pty_nm = ET.SubElement(initg_pty, "Nm")
        initg_pty_nm.text = "Rabobank Nederland"
        initg_pty_id = ET.SubElement(initg_pty, "Id")
        org_id = ET.SubElement(initg_pty_id, "OrgId")
        bic_initg = ET.SubElement(org_id, "BIC")
        bic_initg.text = "RABONL2U"
        
        # Statement
        stmt = ET.SubElement(bk_to_cstmr_stmt, "Stmt")
        
        # Statement ID
        stmt_id = ET.SubElement(stmt, "Id")
        stmt_id.text = statement.statement_number
        
        # Creation date
        cre_dt_tm_stmt = ET.SubElement(stmt, "CreDtTm")
        cre_dt_tm_stmt.text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        # Account
        acct = ET.SubElement(stmt, "Acct")
        acct_id = ET.SubElement(acct, "Id")
        iban = ET.SubElement(acct_id, "IBAN")
        iban.text = statement.account_number
        
        ccy = ET.SubElement(acct, "Ccy")
        ccy.text = statement.currency
        
        # Account owner
        ownr = ET.SubElement(acct, "Ownr")
        nm = ET.SubElement(ownr, "Nm")
        nm.text = "Rabobank"
        
        # Account servicer (the bank)
        svcr = ET.SubElement(acct, "Svcr")
        fin_instn_id = ET.SubElement(svcr, "FinInstnId")
        bic = ET.SubElement(fin_instn_id, "BIC")
        bic.text = "RABONL2U"  # Rabobank BIC
        nm_bank = ET.SubElement(fin_instn_id, "Nm")
        nm_bank.text = "Rabobank Nederland"
        
        # Balance
        bal = ET.SubElement(stmt, "Bal")
        tp = ET.SubElement(bal, "Tp")
        cd_or_prtry = ET.SubElement(tp, "CdOrPrtry")
        cd = ET.SubElement(cd_or_prtry, "Cd")
        cd.text = "CLBD"  # Closing booked
        
        amt = ET.SubElement(bal, "Amt")
        amt.set("Ccy", statement.currency)
        amt.text = f"{abs(statement.closing_balance):.2f}"
        
        cdt_dbt_ind = ET.SubElement(bal, "CdtDbtInd")
        cdt_dbt_ind.text = "CRDT" if statement.closing_balance >= 0 else "DBIT"
        
        dt = ET.SubElement(bal, "Dt")
        dt_val = ET.SubElement(dt, "Dt")
        dt_val.text = (statement.date or datetime.now()).strftime("%Y-%m-%d")
        
        # Transactions
        for i, transaction in enumerate(statement.transactions):
            self._add_transaction(stmt, transaction, i + 1)
        
        # Convert to pretty XML string
        rough_string = ET.tostring(root, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def _add_transaction(self, stmt_element: ET.Element, transaction: Transaction, seq_num: int):
        """Add a transaction entry to the statement."""
        ntry = ET.SubElement(stmt_element, "Ntry")
        
        # Amount
        amt = ET.SubElement(ntry, "Amt")
        amt.set("Ccy", "EUR")
        amt.text = f"{abs(transaction.amount):.2f}"
        
        # Credit/Debit indicator
        cdt_dbt_ind = ET.SubElement(ntry, "CdtDbtInd")
        cdt_dbt_ind.text = "CRDT" if transaction.amount >= 0 else "DBIT"
        
        # Status
        sts = ET.SubElement(ntry, "Sts")
        sts.text = "BOOK"  # Booked
        
        # Booking date
        book_dt = ET.SubElement(ntry, "BookgDt")
        dt = ET.SubElement(book_dt, "Dt")
        dt.text = transaction.date.strftime("%Y-%m-%d")
        
        # Value date
        val_dt = ET.SubElement(ntry, "ValDt")
        dt_val = ET.SubElement(val_dt, "Dt")
        dt_val.text = transaction.date.strftime("%Y-%m-%d")
        
        # Account servicer reference (make it look more like Rabobank format)
        acct_svcr_ref = ET.SubElement(ntry, "AcctSvcrRef")
        acct_svcr_ref.text = transaction.reference or f"RABO{seq_num:010d}"
        
        # Transaction details
        ntry_dtls = ET.SubElement(ntry, "NtryDtls")
        txn_dtls = ET.SubElement(ntry_dtls, "TxDtls")
        
        # References
        refs = ET.SubElement(txn_dtls, "Refs")
        end_to_end_id = ET.SubElement(refs, "EndToEndId")
        end_to_end_id.text = transaction.reference or f"E2E{seq_num:06d}"
        
        # Transaction ID
        txn_id = ET.SubElement(refs, "TxId")
        txn_id.text = f"RABO{seq_num:010d}"
        
        # Instruction ID
        instr_id = ET.SubElement(refs, "InstrId")
        instr_id.text = f"INSTR{seq_num:06d}"
        
        # Related parties (counter account)
        if transaction.counter_account:
            rltd_pties = ET.SubElement(txn_dtls, "RltdPties")
            dbtr_acct = ET.SubElement(rltd_pties, "DbtrAcct")
            dbtr_id = ET.SubElement(dbtr_acct, "Id")
            dbtr_iban = ET.SubElement(dbtr_id, "IBAN")
            dbtr_iban.text = transaction.counter_account
        
        # Remittance information
        rmt_inf = ET.SubElement(txn_dtls, "RmtInf")
        ustrd = ET.SubElement(rmt_inf, "Ustrd")
        ustrd.text = transaction.description[:140]  # CAMT.053 limit
        
        # Bank transaction code
        bank_tx_cd = ET.SubElement(txn_dtls, "BkTxCd")
        domn = ET.SubElement(bank_tx_cd, "Domn")
        cd = ET.SubElement(domn, "Cd")
        cd.text = "PMNT"  # Payment
        
        fmly = ET.SubElement(domn, "Fmly")
        cd_fmly = ET.SubElement(fmly, "Cd")
        
        # Map transaction types to CAMT codes
        if transaction.transaction_type == "CARD":
            cd_fmly.text = "CCRD"  # Credit card
        elif transaction.transaction_type == "TRANSFER":
            cd_fmly.text = "ICDT"  # Instant credit transfer
        elif transaction.transaction_type == "DIRECT_DEBIT":
            cd_fmly.text = "DDBT"  # Direct debit
        else:
            cd_fmly.text = "TRAF"  # Transfer