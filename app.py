import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO
import re

def extract_transactions(pdf_file):
    """
    Parses a PDF file to extract stock buy and sell transactions.
    This version isolates the transaction text block and processes it as a whole,
    making it robust against multi-line entries and complex spacing.

    Args:
        pdf_file: A file-like object representing the PDF.

    Returns:
        A pandas DataFrame containing the extracted transactions,
        or None if no transactions are found.
    """
    transactions = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # Use tolerance to improve layout accuracy during text extraction
                text = page.extract_text(x_tolerance=2, y_tolerance=2) 
                
                if not text or "交易-股票和股票期權" not in text:
                    continue

                # --- Isolate the relevant text block to process ---
                try:
                    # The transaction data is between the table header and the totals summary.
                    start_marker = "變動金額" # This is the last column header.
                    end_marker = "成交金額合計:"
                    
                    start_index = text.find(start_marker)
                    if start_index == -1:
                        continue # If the header isn't found, skip page.
                    
                    start_index += len(start_marker)

                    end_index = text.find(end_marker)
                    if end_index == -1:
                        # Fallback marker if the primary one isn't on the page.
                        end_marker = "交易-基金"
                        end_index = text.find(end_marker)

                    # Slice the text to get only the part with transaction entries.
                    transaction_block = text[start_index:end_index] if end_index != -1 else text[start_index:]
                    
                    # Split the block by transaction keywords. This correctly groups 
                    # multi-line stock names with their parent transaction.
                    individual_transactions = re.split(r'(?=賣出平倉|買入開倉)', transaction_block)

                    for trans_text in individual_transactions:
                        if not trans_text.strip():
                            continue
                        
                        # Clean the text: replace all newlines and multiple spaces with a single space.
                        # This creates a predictable, single-line string for each transaction.
                        clean_text = ' '.join(trans_text.split())

                        # A flexible regex to find the transaction parts in the cleaned string.
                        pattern = re.compile(
                            r"(賣出平倉|買入開倉)\s+(.*?)\s+([A-Z]{3})\s+.*?"  # Action, Stock Name (non-greedy), Currency
                            r"([\d,.]+)\s+([\d,.]+)\s+"                      # Price and Quantity (any order)
                            r"(-?[\d,.]+)\s+(-?[\d,.]+)"                     # Amount and Change
                        )
                        match = pattern.search(clean_text)

                        if match:
                            try:
                                action_chinese = match.group(1)
                                name_code = match.group(2)
                                currency = match.group(3)
                                
                                # The next four captured groups are our numbers
                                val1_str = match.group(4).replace(',', '')
                                val2_str = match.group(5).replace(',', '')
                                amount_str = match.group(6).replace(',', '')
                                change_str = match.group(7).replace(',', '')

                                action = "Sell" if "賣出平倉" in action_chinese else "Buy"

                                val1 = float(val1_str)
                                val2 = float(val2_str)

                                # The value with a decimal point is the price; the other is quantity.
                                price = val1 if '.' in val1_str else val2
                                quantity = val2 if '.' in val1_str else val1
                                
                                amount = float(amount_str)
                                change = float(change_str)

                                transactions.append({
                                    "Action": action,
                                    "Stock Name": name_code,
                                    "Quantity": int(quantity),
                                    "Price": price,
                                    "Amount": amount,
                                    "Currency": currency,
                                    "Net Change": change
                                })
                            except (ValueError, IndexError, TypeError):
                                # If parsing the numbers fails for this entry, skip it.
                                continue
                except Exception:
                    # If processing the block fails, move to the next page.
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
        st.warning("No stock transactions could be found in the uploaded PDF. Please ensure the PDF contains a '交易-股票和股票期權' (Transactions - Stocks and Stock Options) section with valid trade entries.")

st.markdown("---")
st.markdown("Created with [Streamlit](https://streamlit.io).")

