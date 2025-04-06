import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import PyPDF2
import pytesseract
from PIL import Image
import json
import base64
import requests
from datetime import datetime
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set Page Configuration
st.set_page_config(page_title="Advanced Web Portal", page_icon="🚀", layout="wide")

# GitHub Configuration
if "GITHUB_TOKEN" not in st.secrets:
    st.error("GitHub token not found in secrets. Please add it to your Streamlit secrets.")
    github_enabled = False
else:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets.get("GITHUB_REPO", "asif-3/as")  # Allow repo config in secrets
    github_enabled = True

# Create cache directory
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def push_to_github(file_path, repo_path, commit_message, retry_count=3):
    """
    Push file to GitHub repo using GitHub API with improved error handling and retries.
    
    Args:
        file_path: Local path to the file
        repo_path: Path where file should be stored in the repo
        commit_message: Git commit message
        retry_count: Number of retries on failure
        
    Returns:
        tuple: (success_boolean, message)
    """
    if not github_enabled:
        return False, "GitHub integration is disabled. Check your secrets configuration."
    
    try:
        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Check if file exists and get SHA if it does
        for attempt in range(retry_count):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    # File exists, include SHA for update
                    sha = response.json()["sha"]
                    data = {
                        "message": commit_message,
                        "content": content,
                        "sha": sha
                    }
                elif response.status_code == 404:
                    # File doesn't exist yet
                    data = {
                        "message": commit_message,
                        "content": content
                    }
                else:
                    logger.warning(f"GitHub API returned status {response.status_code}: {response.text}")
                    if attempt < retry_count - 1:
                        time.sleep(1)  # Wait before retry
                        continue
                    return False, f"GitHub API error: {response.status_code} - {response.text}"
                
                break  # Successful response, exit retry loop
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt+1}/{retry_count}): {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(1)  # Wait before retry
                    continue
                return False, f"Request error: {str(e)}"
        
        # Put the file to GitHub
        for attempt in range(retry_count):
            try:
                result = requests.put(url, headers=headers, json=data, timeout=10)
                
                if result.status_code in [200, 201]:
                    return True, "File successfully pushed to GitHub"
                else:
                    logger.warning(f"GitHub API returned status {result.status_code}: {result.text}")
                    if attempt < retry_count - 1:
                        time.sleep(1)  # Wait before retry
                        continue
                    return False, f"GitHub API error: {result.status_code} - {result.text}"
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt+1}/{retry_count}): {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(1)  # Wait before retry
                    continue
                return False, f"Request error: {str(e)}"
    
    except Exception as e:
        logger.error(f"Error in push_to_github: {str(e)}")
        return False, f"Error: {str(e)}"

def save_and_push(file_path, repo_path, commit_message):
    """
    Save file locally and push to GitHub with improved error handling.
    Returns a tuple of (success_boolean, message)
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Check if the file already exists and has content
        file_exists = os.path.exists(file_path)
        
        if file_exists:
            # Make sure we don't corrupt existing data
            temp_path = f"{file_path}.temp"
            with open(file_path, "rb") as src:
                with open(temp_path, "wb") as dest:
                    dest.write(src.read())
                    
            # Validate the temp file is good before replacing original
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                os.replace(temp_path, file_path)
            else:
                return False, "Error saving file: temporary file validation failed"
        
        # Push to GitHub if enabled
        if github_enabled:
            success, message = push_to_github(file_path, repo_path, commit_message)
            if not success:
                logger.warning(f"GitHub push failed: {message}")
                # Continue with local storage even if GitHub fails
            return success, message
        return True, "File saved locally (GitHub integration disabled)"
        
    except Exception as e:
        logger.error(f"Error in save_and_push: {str(e)}")
        return False, f"Error: {str(e)}"

# Function to safely read file content
def safe_read_file(file_path):
    if not os.path.exists(file_path):
        return ""
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            return file.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return f"Error reading file: {str(e)}"

# Sidebar - Navigation
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", [
    "📝 Notes App", "📈 Data Visualizer", "📂 File Uploader",
    "🔢 Text Analyzer", "🧮 Calculator"])

# GitHub Status Indicator
with st.sidebar.expander("GitHub Connection Status"):
    if github_enabled:
        st.success("GitHub Integration: Active")
        st.write(f"Repository: {GITHUB_REPO}")
    else:
        st.error("GitHub Integration: Disabled")
        st.write("Check Streamlit secrets configuration")

# ------------------------ 📝 Notes App ------------------------
if page == "📝 Notes App":
    st.title("📝 Notes App")
    notes_file = os.path.join(CACHE_DIR, "notes.txt")
    
    # Create tabs for writing and viewing
    write_tab, view_tab = st.tabs(["Write Notes", "View Notes"])
    
    with write_tab:
        note = st.text_area("Write your note:", height=150)
        col1, col2 = st.columns([1, 4])
        
        with col1:
            timestamp = st.checkbox("Add timestamp", value=True)
        
        if st.button("Save Note"):
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(notes_file), exist_ok=True)
                
                # Create the note with optional timestamp
                formatted_note = note
                if timestamp:
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    formatted_note = f"[{current_time}]\n{note}"
                
                # Append to file with proper separator
                with open(notes_file, "a") as file:
                    file.write(formatted_note + "\n" + "-"*40 + "\n")
                
                # Push to GitHub
                success, message = save_and_push(notes_file, f"data/notes.txt", "Add note")
                
                if success:
                    st.success("Note saved successfully!")
                else:
                    st.warning(f"Note saved locally, but GitHub sync failed: {message}")
                    
            except Exception as e:
                st.error(f"Error saving note: {str(e)}")
    
    with view_tab:
        st.subheader("📜 Your Saved Notes:")
        notes_content = safe_read_file(notes_file)
        if notes_content:
            st.text_area("", value=notes_content, height=400, disabled=True)
        else:
            st.info("No saved notes found.")
        
        if st.button("Refresh Notes"):
            st.experimental_rerun()

# ------------------------ 📈 Data Visualizer ------------------------
elif page == "📈 Data Visualizer":
    st.title("📈 Data Visualization Dashboard")
    
    # Create tabs for file upload and visualization
    upload_tab, visualize_tab = st.tabs(["Upload Data", "Visualize"])
    
    with upload_tab:
        uploaded_file = st.file_uploader("Upload CSV, Excel, or JSON file", type=["csv", "xlsx", "json"])
        
        if uploaded_file is not None:
            # Create directory for uploaded files
            uploaded_dir = os.path.join(CACHE_DIR, "uploaded")
            os.makedirs(uploaded_dir, exist_ok=True)
            
            # Generate unique filename with timestamp to prevent overwrites
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_filename = uploaded_file.name
            safe_filename = f"{timestamp}_{original_filename}"
            uploaded_path = os.path.join(uploaded_dir, safe_filename)
            
            # Save file locally
            try:
                with open(uploaded_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Store the file path in session state for later use
                if "uploaded_files" not in st.session_state:
                    st.session_state.uploaded_files = []
                
                # Add to list of uploaded files with metadata
                file_info = {
                    "original_name": original_filename,
                    "path": uploaded_path,
                    "timestamp": timestamp,
                    "size": os.path.getsize(uploaded_path)
                }
                st.session_state.uploaded_files.append(file_info)
                
                # Push to GitHub with retry logic
                success, message = save_and_push(uploaded_path, f"data/uploaded/{safe_filename}", 
                                                f"Upload data file: {original_filename}")
                
                if success:
                    st.success(f"File uploaded successfully: {original_filename}")
                else:
                    st.warning(f"File saved locally, but GitHub sync failed: {message}")
                
                # Try to load the data based on file type
                try:
                    if original_filename.endswith(".csv"):
                        df = pd.read_csv(uploaded_path)
                        st.session_state.current_df = df
                        st.success("CSV file loaded successfully!")
                    elif original_filename.endswith(".xlsx"):
                        df = pd.read_excel(uploaded_path, engine='openpyxl')
                        st.session_state.current_df = df
                        st.success("Excel file loaded successfully!")
                    elif original_filename.endswith(".json"):
                        df = pd.read_json(uploaded_path)
                        st.session_state.current_df = df
                        st.success("JSON file loaded successfully!")
                    
                    # Show data preview
                    st.subheader("📄 Data Preview")
                    st.dataframe(df.head())
                    
                except Exception as e:
                    st.error(f"Error processing file: {str(e)}")
            
            except Exception as e:
                st.error(f"Error saving file: {str(e)}")
    
    with visualize_tab:
        # Check if data is loaded
        if "current_df" in st.session_state:
            df = st.session_state.current_df
            
            st.subheader("📊 Visualization Options")
            
            # Display data info
            with st.expander("Data Information"):
                st.write(f"**Rows:** {df.shape[0]}")
                st.write(f"**Columns:** {df.shape[1]}")
                st.write("**Column Types:**")
                st.write(df.dtypes)
            
            # Get column lists for visualization
            numeric_columns = df.select_dtypes(include=np.number).columns.tolist()
            all_columns = df.columns.tolist()
            
            if not numeric_columns:
                st.warning("No numeric columns found for visualization.")
            else:
                # Chart options
                chart_type = st.selectbox("Select chart type", 
                                        ["Line Chart", "Bar Chart", "Area Chart", 
                                        "Histogram", "Pie Chart", "Scatter Plot"])
                
                # Select columns based on chart type
                if chart_type in ["Histogram"]:
                    y_axis = st.selectbox("Select column for analysis", options=numeric_columns)
                    if st.button("Generate Chart"):
                        try:
                            fig, ax = plt.subplots(figsize=(10, 6))
                            ax.hist(df[y_axis].dropna(), bins=20)
                            ax.set_xlabel(y_axis)
                            ax.set_ylabel("Frequency")
                            ax.set_title(f"Histogram of {y_axis}")
                            st.pyplot(fig)
                        except Exception as e:
                            st.error(f"Error generating chart: {str(e)}")
                
                elif chart_type in ["Line Chart", "Bar Chart", "Area Chart", "Scatter Plot"]:
                    x_axis = st.selectbox("X-axis", options=all_columns)
                    y_axis = st.selectbox("Y-axis", options=numeric_columns)
                    
                    if st.button("Generate Chart"):
                        try:
                            if chart_type == "Line Chart":
                                st.line_chart(df[[x_axis, y_axis]].set_index(x_axis))
                            elif chart_type == "Bar Chart":
                                st.bar_chart(df[[x_axis, y_axis]].set_index(x_axis))
                            elif chart_type == "Area Chart":
                                st.area_chart(df[[x_axis, y_axis]].set_index(x_axis))
                            elif chart_type == "Scatter Plot":
                                fig, ax = plt.subplots(figsize=(10, 6))
                                ax.scatter(df[x_axis], df[y_axis])
                                ax.set_xlabel(x_axis)
                                ax.set_ylabel(y_axis)
                                ax.set_title(f"{y_axis} vs {x_axis}")
                                st.pyplot(fig)
                        except Exception as e:
                            st.error(f"Error generating chart: {str(e)}")
                
                elif chart_type == "Pie Chart":
                    x_axis = st.selectbox("Categories", options=all_columns)
                    y_axis = st.selectbox("Values", options=numeric_columns)
                    
                    if st.button("Generate Chart"):
                        try:
                            # Check if there are too many categories
                            if df[x_axis].nunique() <= 10:
                                pie_data = df.groupby(x_axis)[y_axis].sum()
                                fig, ax = plt.subplots(figsize=(10, 6))
                                ax.pie(pie_data, labels=pie_data.index, autopct="%1.1f%%", startangle=90)
                                ax.axis("equal")
                                st.pyplot(fig)
                            else:
                                st.warning(f"Too many categories ({df[x_axis].nunique()}) for a pie chart. Consider selecting a column with 10 or fewer unique values.")
                        except Exception as e:
                            st.error(f"Error generating chart: {str(e)}")
        else:
            st.info("Please upload a data file in the 'Upload Data' tab first.")

# ------------------------ 📂 File Uploader ------------------------
elif page == "📂 File Uploader":
    st.title("📂 File Uploader & Viewer")
    
    # Create tabs for upload and file management
    upload_tab, manage_tab = st.tabs(["Upload Files", "Manage Files"])
    
    with upload_tab:
        uploaded_file = st.file_uploader("Upload any file", type=None)
        
        if uploaded_file is not None:
            # Create directory for uploaded files
            uploaded_dir = os.path.join(CACHE_DIR, "files")
            os.makedirs(uploaded_dir, exist_ok=True)
            
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_filename = uploaded_file.name
            safe_filename = f"{timestamp}_{original_filename}"
            file_path = os.path.join(uploaded_dir, safe_filename)
            
            try:
                # Save file locally
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Keep track of uploaded files
                if "uploaded_file_list" not in st.session_state:
                    st.session_state.uploaded_file_list = []
                
                # Add to list with metadata
                file_info = {
                    "original_name": original_filename,
                    "path": file_path,
                    "timestamp": timestamp,
                    "size": os.path.getsize(file_path),
                    "extension": original_filename.split('.')[-1].lower() if '.' in original_filename else "unknown"
                }
                st.session_state.uploaded_file_list.append(file_info)
                
                # Push to GitHub
                success, message = save_and_push(file_path, f"data/files/{safe_filename}", 
                                               f"Upload file: {original_filename}")
                
                if success:
                    st.success(f"File uploaded successfully: {original_filename}")
                else:
                    st.warning(f"File saved locally, but GitHub sync failed: {message}")
                
                # Process file based on extension
                file_extension = original_filename.split('.')[-1].lower() if '.' in original_filename else "unknown"
                
                try:
                    if file_extension in ["txt", "csv", "json"]:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                            st.subheader("📖 File Contents:")
                            content = file.read()
                            st.text_area("", value=content, height=300, disabled=True)
                    
                    elif file_extension in ["jpg", "jpeg", "png"]:
                        image = Image.open(file_path)
                        st.subheader("🖼️ Image Preview:")
                        st.image(image, caption=original_filename, use_container_width=True)
                        
                        # Attempt OCR
                        with st.expander("Image Text Recognition"):
                            try:
                                text = pytesseract.image_to_string(image)
                                if text.strip():
                                    st.write("Detected Text:")
                                    st.text_area("", value=text, height=150)
                                else:
                                    st.info("No text detected in the image.")
                            except Exception as e:
                                st.error(f"OCR error: {str(e)}")
                    
                    elif file_extension == "pdf":
                        try:
                            pdf_reader = PyPDF2.PdfReader(file_path)
                            num_pages = len(pdf_reader.pages)
                            
                            st.subheader(f"📄 PDF Document ({num_pages} pages)")
                            
                            # Extract text from selected pages
                            with st.expander("Extract Text"):
                                page_range = st.slider("Select page range", 1, max(1, num_pages), (1, min(5, num_pages)))
                                
                                if st.button("Extract Text"):
                                    text = ""
                                    for i in range(page_range[0]-1, page_range[1]):
                                        page_text = pdf_reader.pages[i].extract_text() or "[No extractable text on page]"
                                        text += f"\n--- Page {i+1} ---\n{page_text}\n"
                                    
                                    st.text_area("Extracted Text:", value=text, height=300)
                        except Exception as e:
                            st.error(f"Error processing PDF: {str(e)}")
                    
                    else:
                        st.info(f"File uploaded successfully. File type: {file_extension}")
                        st.write(f"File size: {file_info['size']} bytes")
                
                except Exception as e:
                    st.error(f"Error processing file: {str(e)}")
            
            except Exception as e:
                st.error(f"Error saving file: {str(e)}")
    
    with manage_tab:
        st.subheader("📁 Uploaded Files")
        
        if "uploaded_file_list" in st.session_state and st.session_state.uploaded_file_list:
            files = st.session_state.uploaded_file_list
            
            for i, file_info in enumerate(files):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"**{file_info['original_name']}**")
                    st.write(f"Uploaded: {datetime.strptime(file_info['timestamp'], '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col2:
                    st.write(f"Type: {file_info['extension']}")
                    st.write(f"Size: {file_info['size']} bytes")
                
                with col3:
                    if st.button(f"View", key=f"view_{i}"):
                        # Set current file to view
                        st.session_state.current_file = file_info
                        st.experimental_rerun()
            
            # Show selected file if any
            if "current_file" in st.session_state:
                file_info = st.session_state.current_file
                st.subheader(f"Viewing: {file_info['original_name']}")
                
                file_extension = file_info['extension']
                file_path = file_info['path']
                
                try:
                    if file_extension in ["txt", "csv", "json"]:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                            content = file.read()
                            st.text_area("Content:", value=content, height=300, disabled=True)
                    
                    elif file_extension in ["jpg", "jpeg", "png"]:
                        image = Image.open(file_path)
                        st.image(image, caption=file_info['original_name'], use_container_width=True)
                    
                    elif file_extension == "pdf":
                        st.write("PDF file - text preview:")
                        try:
                            pdf_reader = PyPDF2.PdfReader(file_path)
                            text = ""
                            for i, page in enumerate(pdf_reader.pages[:2]):  # Preview first 2 pages
                                page_text = page.extract_text() or "[No extractable text]"
                                text += f"\n--- Page {i+1} ---\n{page_text}\n"
                            
                            st.text_area("", value=text, height=200, disabled=True)
                            if len(pdf_reader.pages) > 2:
                                st.info(f"Showing preview of first 2 pages out of {len(pdf_reader.pages)} total pages.")
                        except Exception as e:
                            st.error(f"Error previewing PDF: {str(e)}")
                    
                    else:
                        st.info(f"File type {file_extension} cannot be previewed.")
                
                except Exception as e:
                    st.error(f"Error previewing file: {str(e)}")
        else:
            st.info("No files uploaded yet.")

# ------------------------ 🔢 Text Analyzer ------------------------
elif page == "🔢 Text Analyzer":
    st.title("🔢 Text Analyzer")
    
    # Create tabs for different analysis types
    analyze_tab, summarize_tab = st.tabs(["Word Analysis", "Text Summarization"])
    
    with analyze_tab:
        st.subheader("Word & Character Analysis")
        user_text = st.text_area("Enter text here:", height=150)
        
        if st.button("Analyze Text"):
            if user_text:
                # Word analysis
                words = user_text.split()
                word_count = len(words)
                
                # Character analysis
                char_count = len(user_text)
                char_no_spaces = len(user_text.replace(" ", ""))
                
                # Sentence analysis
                sentences = [s for s in user_text.split('.') if s.strip()]
                sentence_count = len(sentences)
                
                # Display results
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Words", word_count)
                    st.metric("Avg Word Length", round(char_no_spaces / max(1, word_count), 1))
                
                with col2:
                    st.metric("Characters", char_count)
                    st.metric("Chars (no spaces)", char_no_spaces)
                
                with col3:
                    st.metric("Sentences", sentence_count)
                    st.metric("Avg Sentence Length", round(word_count / max(1, sentence_count), 1))
                
                # Word frequency analysis
                with st.expander("Word Frequency"):
                    # Remove punctuation and convert to lowercase
                    import re
                    clean_text = re.sub(r'[^\w\s]', '', user_text.lower())
                    words = clean_text.split()
                    
                    # Get word frequency
                    from collections import Counter
                    word_freq = Counter(words)
                    
                    # Display top words
                    st.subheader("Most Common Words")
                    word_data = pd.DataFrame(word_freq.most_common(10), columns=["Word", "Count"])
                    
                    col1, col2 = st.columns([3, 2])
                    
                    with col1:
                        st.dataframe(word_data)
                    
                    with col2:
                        if len(word_data) > 0:
                            fig, ax = plt.subplots()
                            ax.barh(word_data["Word"][::-1], word_data["Count"][::-1])
                            ax.set_xlabel("Count")
                            st.pyplot(fig)
            else:
                st.warning("Please enter some text to analyze.")
    
    with summarize_tab:
        st.subheader("Text Summarization")
        summary_text = st.text_area("Enter text to summarize:", height=200)
        
        max_sentences = st.slider("Max sentences in summary", 1, 10, 3)
        
        if st.button("Generate Summary"):
            if summary_text:
                # Simple extractive summarization
                sentences = [s.strip() for s in summary_text.split('.') if s.strip()]
                
                if len(sentences) <= max_sentences:
                    st.info("Text is already concise. No summarization needed.")
                    st.write(summary_text)
                else:
                    # Very simple summarization - take first few sentences
                    # In a real app, you might want a more sophisticated approach
                    summary = '. '.join(sentences[:max_sentences]) + '.'
                    
                    st.subheader("📝 Summary:")
                    st.write(summary)
                    
                    # Show stats
                    original_words = len(summary_text.split())
                    summary_words = len(summary.split())
                    reduction = round((1 - summary_words / original_words) * 100, 1)
                    
                    st.write(f"**Original length:** {original_words} words")
                    st.write(f"**Summary length:** {summary_words} words")
                    st.write(f"**Reduction:** {reduction}%")
            else:
                st.warning("Please enter some text to summarize.")

# ------------------------ 🧮 Calculator ------------------------
elif page == "🧮 Calculator":
    st.title("🧮 Calculator App")
    
    # Create tabs for basic and scientific calculators
    basic_tab, scientific_tab = st.tabs(["Basic Calculator", "Scientific Calculator"])
    
    with basic_tab:
        st.subheader("Basic Operations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            num1 = st.number_input("Enter first number", value=0.0)
        
        with col2:
            num2 = st.number_input("Enter second number", value=0.0)
        
        operation = st.radio("Select operation", ["Addition", "Subtraction", "Multiplication", "Division"])
        
        if st.button("Calculate", key="basic_calc"):
            try:
                if operation == "Addition":
                    result = num1 + num2
                    symbol = "+"
                elif operation == "Subtraction":
                    result = num1 - num2
                    symbol = "-"
                elif operation == "Multiplication":
                    result = num1 * num2
                    symbol = "×"
                elif operation == "Division":
                    if num2 == 0:
                        st.error("Error! Division by zero.")
                    else:
                        result = num1 / num2
                        symbol = "÷"
                
                if 'symbol' in locals():  # Only display if no error occurred
                    st.subheader(f"Result: {num1} {symbol} {num2} = {result}")
                    
                    # Save calculation history
                    if "calc_history" not in st.session_state:
                        st.session_state.calc_history = []
                    
                    st.session_state.calc_history.append({
                        "operation": operation,
                        "num1": num1,
                        "num2": num2,
                        "result": result,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            except Exception as e:
                st.error(f"Calculation error: {str(e)}")
        
        # Display calculation history
        if "calc_history" in st.session_state and st.session_state.calc_history
