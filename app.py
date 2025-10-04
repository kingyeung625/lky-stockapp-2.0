import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

def extract_transactions(pdf_file):
    """
    Parses a PDF file to extract stock buy and sell transactions.

    Args:
        pdf_file: A file-like object representing the PDF.

    Returns:
        A pandas DataFrame containing the extracted transactions,
        or None if no transactions are found.
    """
    transactions = []
    # Regex to capture the main transaction details.
    # It looks for "買入開倉" (Buy) or "賣出平倉" (Sell) and captures the subsequent data points.
    transaction_pattern = re.compile(
        r"(賣出平倉|買入開倉)\s+([\w\d\(\)\-\s]+)\s+(HKD|USD|CNH)\s+([\d\.]+)\s+(\d+)\s+([\d,\.]+)\s+([-\d,\.]+)"
    )

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=2, y_tolerance=2)
                if text:
                    # Split text into lines to process them individually
                    lines = text.split('\n')
                    for i, line in enumerate(lines):
                        # The keywords "買入開倉" (Buy to open) and "賣出平倉" (Sell to close) indicate a transaction.
                        if "買入開倉" in line or "賣出平倉" in line:
                            # Sometimes the full transaction data spans multiple lines in the extracted text.
                            # We'll join the current and next line to form a more complete string for the regex.
                            full_line_text = line
                            if i + 1 < len(lines):
                                full_line_text += " " + lines[i+1]
                            
                            match = transaction_pattern.search(full_line_text.replace('\n', ' '))
                            if match:
                                try:
                                    action_chinese = match.group(1)
                                    action = "Sell" if action_chinese == "賣出平倉" else "Buy"
                                    name_code = match.group(2).strip()
                                    currency = match.group(3)
                                    
                                    # In the PDF, quantity and price can be swapped in order.
                                    # We'll check which is which based on typical values.
                                    val1 = float(match.group(4).replace(',', ''))
                                    val2 = float(match.group(5).replace(',', ''))
                                    
                                    price = val1 if '.' in match.group(4) else val2
                                    quantity = val2 if '.' in match.group(4) else val1

                                    amount = float(match.group(6).replace(',', ''))
                                    change = float(match.group(7).replace(',', ''))

                                    transactions.append({
                                        "Action": action,
                                        "Stock Name": name_code,
                                        "Quantity": int(quantity),
                                        "Price": price,
                                        "Amount": amount,
                                        "Currency": currency,
                                        "Net Change": change
                                    })
                                except (ValueError, IndexError):
                                    # Skip lines that look like transactions but can't be parsed
                                    continue

        if transactions:
            return pd.DataFrame(transactions)
        else:
            return None

    except Exception as e:
        st.error(f"An error occurred while processing the PDF: {e}")
        return None

# --- Streamlit App UI ---

st.set_page_config(layout="wide", page_title="Transaction Extractor")

st.title("📈 PDF Statement Transaction Extractor")
st.markdown("""
Upload your daily statement PDF file to automatically extract all your buy and sell stock transactions.
The app will scan the document and display the trades in a clean table below.
""")

# --- Instructions and App Layout ---
with st.expander("How to use this app"):
    st.markdown("""
    1.  **Upload your PDF:** Click on the 'Browse files' button or drag and drop your PDF statement into the designated area.
    2.  **View Transactions:** The app will automatically process the file. If any stock trades are found, they will appear in the 'Extracted Transactions' table.
    3.  **No Data Stored:** Your uploaded file is processed in memory and is not saved or stored anywhere.
    """)

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type="pdf",
    help="Please upload the PDF version of your daily statement."
)

if uploaded_file is not None:
    # To read the uploaded file, we need to wrap it in a BytesIO object
    # because pdfplumber expects a file path or a binary stream.
    bytes_data = uploaded_file.getvalue()
    pdf_stream = BytesIO(bytes_data)

    with st.spinner('Analyzing your statement...'):
        df_transactions = extract_transactions(pdf_stream)

    st.subheader("Extracted Transactions")
    if df_transactions is not None and not df_transactions.empty:
        st.dataframe(
            df_transactions,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Quantity": st.column_config.NumberColumn(format="%d"),
                "Price": st.column_config.NumberColumn(format="$%.4f"),
                "Amount": st.column_config.NumberColumn(format="$%.2f"),
                "Net Change": st.column_config.NumberColumn(format="%.2f"),
            }
        )
    else:
        st.warning("No stock transactions could be found in the uploaded PDF. The tool currently only extracts stock and ETF trades.")

st.markdown("---")
st.markdown("Created with [Streamlit](https://streamlit.io).")
