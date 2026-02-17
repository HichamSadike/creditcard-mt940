"""Generate downloadable Excel template with dummy transactions."""

import io
from datetime import datetime, timedelta

import pandas as pd


def generate_template() -> bytes:
    """Generate an Excel template with dummy transactions and return as bytes.

    The template has 5 example rows so users understand the expected format.
    Users delete the examples, add their own transactions, and re-upload.
    """
    today = datetime.now()

    dummy_data = [
        {
            "Datum": (today - timedelta(days=10)).strftime("%d-%m-%Y"),
            "Bedrag": -49.99,
            "Omschrijving": "Albert Heijn - Boodschappen",
            "Tegenrekening": "NL91ABNA0417164300",
            "Referentie": "AH-001",
        },
        {
            "Datum": (today - timedelta(days=8)).strftime("%d-%m-%Y"),
            "Bedrag": -12.50,
            "Omschrijving": "Spotify Premium maandabonnement",
            "Tegenrekening": "",
            "Referentie": "SPOTIFY-FEB",
        },
        {
            "Datum": (today - timedelta(days=5)).strftime("%d-%m-%Y"),
            "Bedrag": 1500.00,
            "Omschrijving": "Salaris februari 2026",
            "Tegenrekening": "NL20INGB0001234567",
            "Referentie": "SAL-2026-02",
        },
        {
            "Datum": (today - timedelta(days=3)).strftime("%d-%m-%Y"),
            "Bedrag": -85.00,
            "Omschrijving": "Ziggo Internet & TV",
            "Tegenrekening": "NL45RABO0123456789",
            "Referentie": "",
        },
        {
            "Datum": (today - timedelta(days=1)).strftime("%d-%m-%Y"),
            "Bedrag": -29.99,
            "Omschrijving": "bol.com - Bestelling #9283746",
            "Tegenrekening": "",
            "Referentie": "BOL-9283746",
        },
    ]

    df = pd.DataFrame(dummy_data)

    # Write to Excel in memory
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transacties")

        # Auto-fit column widths
        ws = writer.sheets["Transacties"]
        for col_idx, col_name in enumerate(df.columns, 1):
            max_len = max(
                len(str(col_name)),
                *(len(str(v)) for v in df[col_name]),
            )
            ws.column_dimensions[
                ws.cell(row=1, column=col_idx).column_letter
            ].width = max_len + 4

    buf.seek(0)
    return buf.getvalue()
