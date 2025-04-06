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

# Configure GitHub connection settings
@st.cache_resource
def get_github_config():
    """Get GitHub configuration with error handling"""
    try:
        return {
            "token": st.secrets["GITHUB_TOKEN"],
            "repo": st.secrets["GITHUB_REPO"] if "GITHUB_REPO" in st.secrets else "asif-3/as",
            "base_url": "https://api.github.com"
        }
    except Exception as e:
        st.sidebar.error(f"GitHub config error: {str(e)}")
        return None

github_config = get_github_config()

def push_to_github(file_path, repo_path, commit_message):
    """Push file to GitHub repo using GitHub API with improved error handling and retry logic."""
    if not github_config:
        st.warning("GitHub configuration is missing. Data will be saved locally only.")
        return False
    
    try:
        # Read file content
        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        # Setup request
        url = f"{github_config['base_url']}/repos/{github_config['repo']}/contents/{repo_path}"
        headers = {
            "Authorization": f"token {github_config['token']}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Check if file exists
        max_retries = 3
        retry_count = 0
        success = False
        
        while not success and retry_count < max_retries:
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    # File exists, update it
                    sha = response.json()["sha"]
                    data = {
                        "message": commit_message,
                        "content": content,
                        "sha": sha
                    }
                elif response.status_code == 404:
                    # File doesn't exist, create it
                    data = {
                        "message": commit_message,
                        "content": content
                    }
                else:
                    st.error(f"GitHub API error: {response.status_code} - {response.text}")
                    retry_count += 1
                    time.sleep(1)  # Wait before retry
                    continue

                # Push the content
                result = requests.put(url, headers=headers, json=data, timeout=10)
                
                if result.status_code in [200, 201]:
                    success = True
                    return True
                else:
                    st.error(f"Failed to push to GitHub: {result.status_code} - {result.text}")
                    retry_count += 1
                    time.sleep(1)  # Wait before retry
            
            except requests.exceptions.RequestException as e:
                st.error(f"Network error during GitHub push: {str(e)}")
                retry_count += 1
                time.sleep(2)  # Wait before retry
        
        return success
    
    except Exception as e:
        st.error(f"Error pushing to GitHub: {str(e)}")
        return False


def save_file(content, file_path, is_text=True):
    """Save file content ensuring directory exists"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        if is_text:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            with open(file_path, "wb") as f:
                f.write(content)
        
        return True
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return False


def save_and_push(content, file_path, repo_path, commit_message, is_text=True):
    """Save file locally and push to GitHub with improved error handling"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save locally first
    if save_file(content, file_path, is_text):
        st.success("File saved locally.")
        
        # Then push to GitHub if configured
        if github_config:
            with st.spinner("Pushing to GitHub..."):
                if push_to_github(file_path, repo_path, f"{commit_message} - {timestamp}"):
                    st.success("Successfully pushed to GitHub!")
                    return True
                else:
                    st.warning("Failed to push to GitHub, but file was saved locally.")
                    return False
        return True
    else:
        st.error("Failed to save file.")
        return False


# Set Page Configuration
st.set_page_config(page_title="Advanced Web Portal", page_icon="🚀", layout="wide")

# Sidebar - Navigation
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", [
    "📝 Notes App", "📈 Data Visualizer", "📂 File Uploader",
    "🔢 Text Analyzer", "🧮 Calculator"])

# GitHub status indicator in sidebar
if github_config:
    st.sidebar.success("✅ GitHub Integration Active")
else:
    st.sidebar.warning("⚠️ GitHub Integration Inactive - Saving locally only")


# ------------------------ 📝 Notes App ------------------------
if page == "📝 Notes App":
    st.title("📝 Notes App")
    notes_file = "data/notes.txt"
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(notes_file), exist_ok=True)
    
    note = st.text_area("Write your note:", height=150)
    
    if st.button("Save Note"):
        # Read existing notes
        existing_notes = ""
        if os.path.exists(notes_file):
            with open(notes_file, "r", encoding="utf-8", errors="ignore") as file:
                existing_notes = file.read()
        
        # Append new note with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_content = f"{existing_notes}\n[{timestamp}]\n{note}\n{'-'*40}\n"
        
        if save_and_push(new_content, notes_file, "data/notes.txt", "Add note"):
            st.success("Note saved successfully!")
    
    # Display notes if file exists
    if os.path.exists(notes_file):
        with open(notes_file, "r", encoding="utf-8", errors="ignore") as file:
            notes_content = file.read()
            if notes_content.strip():
                st.subheader("📜 Your Saved Notes:")
                st.text(notes_content)
            else:
                st.info("No notes saved yet. Write your first note!")

# ------------------------ 📈 Data Visualizer ------------------------
elif page == "📈 Data Visualizer":
    st.title("📈 Data Visualization Dashboard")
    uploaded_file = st.file_uploader("Upload CSV, Excel, or JSON file", type=["csv", "xlsx", "json"])

    if uploaded_file is not None:
        uploaded_dir = "uploaded"
        os.makedirs(uploaded_dir, exist_ok=True)
        uploaded_path = os.path.join(uploaded_dir, uploaded_file.name)

        # Save the uploaded file
        with open(uploaded_path, "wb") as f:
            file_bytes = uploaded_file.getbuffer()
            f.write(file_bytes)
            
        # Push to GitHub
        with st.spinner("Saving and pushing to GitHub..."):
            push_success = push_to_github(
                uploaded_path, 
                f"uploaded/{uploaded_file.name}", 
                f"Add uploaded file {uploaded_file.name}"
            )
            
            if push_success:
                st.success(f"File '{uploaded_file.name}' uploaded and pushed to GitHub!")
            else:
                st.warning(f"File '{uploaded_file.name}' saved locally but GitHub push failed.")

        try:
            # Process based on file type
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_path)
            elif uploaded_file.name.endswith(".xlsx"):
                df = pd.read_excel(uploaded_path, engine='openpyxl')
            elif uploaded_file.name.endswith(".json"):
                df = pd.read_json(uploaded_path)
            else:
                df = None
                st.error("Unsupported file format for visualization.")

            if df is not None:
                st.subheader("📄 Data Preview")
                st.dataframe(df.head())

                # Get columns suitable for visualization
                numeric_columns = df.select_dtypes(include=np.number).columns.tolist()
                all_columns = df.columns.tolist()

                if not numeric_columns:
                    st.warning("No numeric columns found for visualization.")
                else:
                    st.subheader("📈 Create a Chart")
                    chart_type = st.selectbox("Select chart type", ["Line Chart", "Bar Chart", "Area Chart", "Histogram", "Pie Chart", "Scatter Plot"])
                    
                    # Column selection based on chart type
                    if chart_type in ["Histogram"]:
                        y_axis = st.selectbox("Select data column", options=numeric_columns)
                        x_axis = None
                    elif chart_type in ["Pie Chart"]:
                        x_axis = st.selectbox("Categories", options=all_columns)
                        y_axis = st.selectbox("Values", options=numeric_columns)
                    else:
                        x_axis = st.selectbox("X-axis", options=all_columns)
                        y_axis = st.selectbox("Y-axis", options=numeric_columns)

                    if st.button("Generate Chart"):
                        try:
                            if chart_type == "Line Chart":
                                st.line_chart(df.set_index(x_axis)[y_axis])
                            elif chart_type == "Bar Chart":
                                st.bar_chart(df.set_index(x_axis)[y_axis])
                            elif chart_type == "Area Chart":
                                st.area_chart(df.set_index(x_axis)[y_axis])
                            elif chart_type == "Scatter Plot":
                                fig, ax = plt.subplots()
                                ax.scatter(df[x_axis], df[y_axis])
                                ax.set_xlabel(x_axis)
                                ax.set_ylabel(y_axis)
                                ax.set_title(f"{x_axis} vs {y_axis}")
                                st.pyplot(fig)
                            elif chart_type == "Histogram":
                                fig, ax = plt.subplots()
                                ax.hist(df[y_axis].dropna(), bins=min(20, len(df[y_axis].unique())))
                                ax.set_xlabel(y_axis)
                                ax.set_title(f"Histogram of {y_axis}")
                                st.pyplot(fig)
                            elif chart_type == "Pie Chart":
                                if df[x_axis].nunique() <= 10:
                                    pie_data = df.groupby(x_axis)[y_axis].sum()
                                    fig, ax = plt.subplots()
                                    ax.pie(pie_data, labels=pie_data.index, autopct="%1.1f%%", startangle=90)
                                    ax.axis("equal")
                                    st.pyplot(fig)
                                else:
                                    st.warning("Pie chart works best with fewer than 10 unique categories. Consider aggregating your data.")
                        except Exception as e:
                            st.error(f"Error generating chart: {str(e)}")
                            st.info("Tip: Check if your column selections are appropriate for the selected chart type.")

        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            st.info("Make sure your file has the correct format and encoding.")

# ------------------------ 📂 File Uploader ------------------------
elif page == "📂 File Uploader":
    st.title("📂 File Uploader & Viewer")
    uploaded_file = st.file_uploader("Upload any file", type=None)
    
    if uploaded_file is not None:
        uploaded_dir = "uploaded"
        os.makedirs(uploaded_dir, exist_ok=True)
        file_path = os.path.join(uploaded_dir, uploaded_file.name)

        # Save the file locally
        with open(file_path, "wb") as f:
            file_bytes = uploaded_file.getbuffer()
            f.write(file_bytes)
            file_size = len(file_bytes)
        
        # Push to GitHub with size check (GitHub API has limitations)
        if file_size > 100 * 1024 * 1024:  # 100MB limit
            st.warning("File is too large to push to GitHub (>100MB). Saved locally only.")
        else:
            with st.spinner("Pushing to GitHub..."):
                push_success = push_to_github(
                    file_path, 
                    f"uploaded/{uploaded_file.name}", 
                    f"Add uploaded file {uploaded_file.name}"
                )
                
                if push_success:
                    st.success(f"File '{uploaded_file.name}' uploaded and pushed to GitHub!")
                else:
                    st.warning(f"File '{uploaded_file.name}' saved locally but GitHub push failed.")

        # Display file information
        st.write(f"**File name:** {uploaded_file.name}")
        st.write(f"**File size:** {file_size / 1024:.2f} KB")
        
        # Process file based on extension
        file_extension = uploaded_file.name.split('.')[-1].lower() if '.' in uploaded_file.name else ""
        
        try:
            if file_extension in ["txt", "csv", "json", "py", "html", "css", "js", "md"]:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                    content = file.read()
                    st.subheader("📖 File Contents:")
                    st.code(content)
            elif file_extension in ["jpg", "jpeg", "png", "gif"]:
                try:
                    image = Image.open(file_path)
                    st.image(image, caption=f"Uploaded Image: {uploaded_file.name}", use_container_width=True)
                    st.success("Image loaded successfully!")
                    
                    # OCR for images
                    with st.expander("🔍 Image Text Recognition (OCR)"):
                        try:
                            text = pytesseract.image_to_string(image)
                            if text.strip():
                                st.write("Detected Text:")
                                st.code(text)
                            else:
                                st.info("No text detected in this image.")
                        except Exception as e:
                            st.error(f"OCR processing error: {str(e)}")
                            st.info("Make sure Tesseract OCR is properly installed on the server.")
                except Exception as e:
                    st.error(f"Error loading image: {str(e)}")
                    
            elif file_extension == "pdf":
                try:
                    with st.expander("📄 PDF Content"):
                        pdf_reader = PyPDF2.PdfReader(file_path)
                        num_pages = len(pdf_reader.pages)
                        st.write(f"PDF has {num_pages} pages")
                        
                        for i, page in enumerate(pdf_reader.pages):
                            text = page.extract_text()
                            if text:
                                with st.expander(f"Page {i+1}"):
                                    st.write(text)
                except Exception as e:
                    st.error(f"Error reading PDF: {str(e)}")
            else:
                st.info(f"File '{uploaded_file.name}' uploaded successfully. Preview not available for this file type.")
                
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

# ------------------------ 🔢 Text Analyzer ------------------------
elif page == "🔢 Text Analyzer":
    st.title("🔢 Text Analyzer")
    
    user_text = st.text_area("Enter text here:", height=200)
    
    col1, col2 = st.columns(2)
    analyze_button = col1.button("Analyze Text")
    save_button = col2.button("Save Analysis")
    
    if analyze_button or save_button:
        if not user_text.strip():
            st.warning("Please enter some text to analyze.")
        else:
            # Basic text analysis
            word_count = len(user_text.split())
            char_count = len(user_text)
            char_no_spaces = len(user_text.replace(" ", ""))
            sentences = [s for s in user_text.split(". ") if s]
            sentence_count = len(sentences)
            
            # Word frequency
            words = user_text.lower().split()
            word_freq = {}
            for word in words:
                # Clean word of punctuation
                word = word.strip('.,;:!?()[]{}""\'')
                if word and len(word) > 1:  # Ignore empty strings and single characters
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Sort by frequency
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # Generate summary (first 3 sentences or 20% of content)
            summary_length = max(1, min(3, int(sentence_count * 0.2)))
            summary = ". ".join(sentences[:summary_length])
            if not summary.endswith("."):
                summary += "."
                
            # Display analysis
            st.subheader("📊 Text Analysis")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Words", word_count)
            col2.metric("Characters", char_count)
            col3.metric("Sentences", sentence_count)
            
            st.subheader("📝 Summary")
            st.write(summary)
            
            st.subheader("📊 Word Frequency")
            if top_words:
                # Create a DataFrame for display
                freq_df = pd.DataFrame(top_words, columns=["Word", "Frequency"])
                st.dataframe(freq_df)
                
                # Create a simple bar chart
                fig, ax = plt.subplots()
                ax.bar([word for word, _ in top_words[:5]], [freq for _, freq in top_words[:5]])
                ax.set_title("Top 5 Words")
                ax.set_ylabel("Frequency")
                plt.xticks(rotation=45)
                st.pyplot(fig)
            else:
                st.info("No meaningful words found for frequency analysis.")
            
            # Save analysis if requested
            if save_button:
                analysis_dir = "data/text_analysis"
                os.makedirs(analysis_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                analysis_file = f"{analysis_dir}/analysis_{timestamp}.txt"
                
                analysis_content = f"""TEXT ANALYSIS - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
===================================================
STATISTICS:
- Words: {word_count}
- Characters (with spaces): {char_count}
- Characters (without spaces): {char_no_spaces}
- Sentences: {sentence_count}

SUMMARY:
{summary}

WORD FREQUENCY (Top 10):
{chr(10).join([f"- {word}: {freq}" for word, freq in top_words])}

===================================================
ORIGINAL TEXT:
{user_text}
"""
                
                if save_and_push(analysis_content, analysis_file, f"data/text_analysis/analysis_{timestamp}.txt", "Add text analysis"):
                    st.success("Analysis saved successfully!")

# ------------------------ 🧮 Calculator ------------------------
elif page == "🧮 Calculator":
    st.title("🧮 Calculator App")
    
    tabs = st.tabs(["Basic Calculator", "Scientific Calculator", "Unit Converter"])
    
    with tabs[0]:  # Basic Calculator
        st.subheader("Basic Operations")
        num1 = st.number_input("Enter first number", value=0.0)
        num2 = st.number_input("Enter second number", value=0.0)
        operation = st.selectbox("Select operation", 
                                ["Addition", "Subtraction", "Multiplication", "Division", "Modulus", "Power"])
        
        if st.button("Calculate", key="basic_calc"):
            try:
                if operation == "Addition":
                    result = num1 + num2
                elif operation == "Subtraction":
                    result = num1 - num2
                elif operation == "Multiplication":
                    result = num1 * num2
                elif operation == "Division":
                    if num2 == 0:
                        st.error("Error! Division by zero.")
                        result = "Undefined"
                    else:
                        result = num1 / num2
                elif operation == "Modulus":
                    if num2 == 0:
                        st.error("Error! Modulus by zero.")
                        result = "Undefined"
                    else:
                        result = num1 % num2
                elif operation == "Power":
                    result = num1 ** num2
                
                if isinstance(result, (int, float)):
                    st.success(f"Result: {result:.6g}")
                else:
                    st.success(f"Result: {result}")
            except Exception as e:
                st.error(f"Calculation error: {str(e)}")
    
    with tabs[1]:  # Scientific Calculator
        st.subheader("Scientific Operations")
        sci_input = st.number_input("Enter number", value=0.0, key="sci_input")
        sci_operation = st.selectbox("Select operation", 
                                    ["Square", "Square Root", "Cube", "Cube Root", "Logarithm (base 10)", 
                                     "Natural Logarithm", "Sine", "Cosine", "Tangent", "Exponential (e^x)"])
        
        if st.button("Compute", key="sci_calc"):
            try:
                if sci_operation == "Square":
                    sci_result = sci_input ** 2
                elif sci_operation == "Square Root":
                    if sci_input < 0:
                        st.error("Cannot calculate square root of a negative number")
                        sci_result = "Undefined"
                    else:
                        sci_result = np.sqrt(sci_input)
                elif sci_operation == "Cube":
                    sci_result = sci_input ** 3
                elif sci_operation == "Cube Root":
                    sci_result = np.cbrt(sci_input)
                elif sci_operation == "Logarithm (base 10)":
                    if sci_input <= 0:
                        st.error("Cannot calculate logarithm of a non-positive number")
                        sci_result = "Undefined"
                    else:
                        sci_result = np.log10(sci_input)
                elif sci_operation == "Natural Logarithm":
                    if sci_input <= 0:
                        st.error("Cannot calculate logarithm of a non-positive number")
                        sci_result = "Undefined"
                    else:
                        sci_result = np.log(sci_input)
                elif sci_operation == "Sine":
                    sci_result = np.sin(sci_input)
                elif sci_operation == "Cosine":
                    sci_result = np.cos(sci_input)
                elif sci_operation == "Tangent":
                    sci_result = np.tan(sci_input)
                elif sci_operation == "Exponential (e^x)":
                    sci_result = np.exp(sci_input)
                
                if isinstance(sci_result, (int, float)):
                    st.success(f"Result: {sci_result:.10g}")
                else:
                    st.success(f"Result: {sci_result}")
            except Exception as e:
                st.error(f"Computation error: {str(e)}")
    
    with tabs[2]:  # Unit Converter
        st.subheader("Unit Converter")
        
        conversion_types = [
            "Length (m ↔ ft)", 
            "Weight/Mass (kg ↔ lb)", 
            "Temperature (°C ↔ °F)",
            "Area (m² ↔ ft²)",
            "Volume (L ↔ gal)",
            "Speed (km/h ↔ mph)"
        ]
        
        conv_type = st.selectbox("Select conversion type", conversion_types)
        
        col1, col2 = st.columns(2)
        
        if conv_type == "Length (m ↔ ft)":
            input_val = col1.number_input("Enter value", value=0.0, key="length_input")
            input_unit = col1.selectbox("From unit", ["meters", "feet"], key="length_from")
            output_unit = col2.selectbox("To unit", ["feet", "meters"], key="length_to")
            
            if st.button("Convert", key="convert_length"):
                if input_unit == "meters" and output_unit == "feet":
                    result = input_val * 3.28084
                    st.success(f"{input_val} meters = {result:.4f} feet")
                elif input_unit == "feet" and output_unit == "meters":
                    result = input_val / 3.28084
                    st.success(f"{input_val} feet = {result:.4f} meters")
                else:
                    st.info(f"Values are the same: {input_val} {input_unit}")
        
        elif conv_type == "Weight/Mass (kg ↔ lb)":
            input_val = col1.number_input("Enter value", value=0.0, key="weight_input")
            input_unit = col1.selectbox("From unit", ["kilograms", "pounds"], key="weight_from")
            output_unit = col2.selectbox("To unit", ["pounds", "kilograms"], key="weight_to")
            
            if st.button("Convert", key="convert_weight"):
                if input_unit == "kilograms" and output_unit == "pounds":
                    result = input_val * 2.20462
                    st.success(f"{input_val} kilograms = {result:.4f} pounds")
                elif input_unit == "pounds" and output_unit == "kilograms":
                    result = input_val / 2.20462
                    st.success(f"{input_val} pounds = {result:.4f} kilograms")
                else:
                    st.info(f"Values are the same: {input_val} {input_unit}")
        
        elif conv_type == "Temperature (°C ↔ °F)":
            input_val = col1.number_input("Enter value", value=0.0, key="temp_input")
            input_unit = col1.selectbox("From unit", ["Celsius", "Fahrenheit"], key="temp_from")
            output_unit = col2.selectbox("To unit", ["Fahrenheit", "Celsius"], key="temp_to")
            
            if st.button("Convert", key="convert_temp"):
                if input_unit == "Celsius" and output_unit == "Fahrenheit":
                    result = (input_val * 9/5) + 32
                    st.success(f"{input_val}°C = {result:.2f}°F")
                elif input_unit == "Fahrenheit" and output_unit == "Celsius":
                    result = (input_val - 32) * 5/9
                    st.success(f"{input_val}°F = {result:.2f}°C")
                else:
                    st.info(f"Values are the same: {input_val}°{input_unit[0]}")

# Footer
st.sidebar.write("---")
st.sidebar.write("📌 Created with ❤️ by **ASIF**")
st.sidebar.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d')}")
