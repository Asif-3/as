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

# Load GitHub Token from Streamlit Secrets
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = "asif-3/as"

def push_to_github(file_path, repo_path, commit_message):
    """Push file to GitHub repo using GitHub API."""
    with open(file_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Check if the file already exists
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        sha = response.json()["sha"]
        data = {
            "message": commit_message,
            "content": content,
            "sha": sha
        }
    else:
        data = {
            "message": commit_message,
            "content": content
        }

    result = requests.put(url, headers=headers, json=data)
    return result.status_code == 201 or result.status_code == 200

# Set Page Configuration
st.set_page_config(page_title="Advanced Web Portal", page_icon="🚀", layout="wide")

# Sidebar - Navigation
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["📝 Notes App", "📈 Data Visualizer", "📂 File Uploader", "🔢 Text Analyzer", "🧮 Calculator"])

# Save file and push to GitHub
def save_and_push(file_path, repo_path, commit_message):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    push_to_github(file_path, repo_path, commit_message)

# ------------------------ 📝 Notes App ------------------------
if page == "📝 Notes App":
    st.title("📝 Notes App")
    notes_file = "data/notes.txt"
    os.makedirs(os.path.dirname(notes_file), exist_ok=True)
    note = st.text_area("Write your note:", height=150)
    if st.button("Save Note"):
        with open(notes_file, "a") as file:
            file.write(note + "\n" + "-"*40 + "\n")
        save_and_push(notes_file, "data/notes.txt", "Add note")
        st.success("Note saved and pushed to GitHub!")
    if os.path.exists(notes_file):
        with open(notes_file, "r") as file:
            st.subheader("📜 Your Saved Notes:")
            st.text(file.read())

# ------------------------ 📈 Data Visualizer ------------------------
elif page == "📈 Data Visualizer":
    st.title("📈 Data Visualization Dashboard")
    uploaded_file = st.file_uploader("Upload CSV, Excel, or JSON file", type=["csv", "xlsx", "json"])

    if uploaded_file is not None:
        uploaded_dir = "uploaded"
        os.makedirs(uploaded_dir, exist_ok=True)
        uploaded_path = os.path.join(uploaded_dir, uploaded_file.name)

        with open(uploaded_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        save_and_push(uploaded_path, f"uploaded/{uploaded_file.name}", f"Add uploaded file {uploaded_file.name}")

        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_path)
            elif uploaded_file.name.endswith(".xlsx"):
                df = pd.read_excel(uploaded_path, engine='openpyxl')
            elif uploaded_file.name.endswith(".json"):
                df = pd.read_json(uploaded_path)
            else:
                df = None

            if df is not None:
                st.subheader("📄 Data Preview")
                st.dataframe(df.head())

                numeric_columns = df.select_dtypes(include=np.number).columns.tolist()
                all_columns = df.columns.tolist()

                if not numeric_columns:
                    st.warning("No numeric columns found for visualization.")
                else:
                    st.subheader("📈 Create a Chart")
                    chart_type = st.selectbox("Select chart type", ["Line Chart", "Bar Chart", "Area Chart", "Histogram", "Pie Chart"])
                    x_axis = st.selectbox("X-axis", options=all_columns)
                    y_axis = st.selectbox("Y-axis", options=numeric_columns)

                    if st.button("Generate Chart"):
                        if chart_type == "Line Chart":
                            st.line_chart(df[[x_axis, y_axis]].set_index(x_axis))
                        elif chart_type == "Bar Chart":
                            st.bar_chart(df[[x_axis, y_axis]].set_index(x_axis))
                        elif chart_type == "Area Chart":
                            st.area_chart(df[[x_axis, y_axis]].set_index(x_axis))
                        elif chart_type == "Histogram":
                            fig, ax = plt.subplots()
                            ax.hist(df[y_axis].dropna(), bins=20)
                            ax.set_xlabel(y_axis)
                            ax.set_title("Histogram")
                            st.pyplot(fig)
                        elif chart_type == "Pie Chart":
                            if df[x_axis].nunique() <= 10:
                                pie_data = df.groupby(x_axis)[y_axis].sum()
                                fig, ax = plt.subplots()
                                ax.pie(pie_data, labels=pie_data.index, autopct="%1.1f%%", startangle=90)
                                ax.axis("equal")
                                st.pyplot(fig)
                            else:
                                st.warning("Pie chart works best with fewer unique categories in the X-axis.")

        except Exception as e:
            st.error(f"Error processing file: {e}")

# ------------------------ 📂 File Uploader ------------------------
elif page == "📂 File Uploader":
    st.title("📂 File Uploader & Viewer")
    uploaded_file = st.file_uploader("Upload any file", type=None)
    if uploaded_file is not None:
        uploaded_dir = "uploaded"
        os.makedirs(uploaded_dir, exist_ok=True)
        file_path = os.path.join(uploaded_dir, uploaded_file.name)

        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        save_and_push(file_path, f"uploaded/{uploaded_file.name}", f"Add uploaded file {uploaded_file.name}")

        file_extension = uploaded_file.name.split('.')[-1].lower()
        try:
            if file_extension in ["txt", "csv", "json"]:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                    st.subheader("📖 File Contents:")
                    st.text(file.read())
            elif file_extension in ["jpg", "jpeg", "png"]:
                image = Image.open(file_path)
                st.image(image, caption="Uploaded Image", use_container_width=True)
                st.success("Image saved successfully!")
                st.subheader("🔍 Image Identification:")
                try:
                    text = pytesseract.image_to_string(image)
                    st.write(f"Detected Text: {text}")
                except Exception as e:
                    st.error(f"Tesseract OCR error: {e}")
            elif file_extension == "pdf":
                pdf_reader = PyPDF2.PdfReader(file_path)
                text = "".join([page.extract_text() for page in pdf_reader.pages if page.extract_text()])
                st.subheader("📄 PDF Extracted Text:")
                st.text(text)
        except Exception as e:
            st.error(f"Error reading file: {e}")

# ------------------------ 🔢 Text Analyzer ------------------------
elif page == "🔢 Text Analyzer":
    st.title("🔢 Text Analyzer (Summarization & Word Counter)")
    user_text = st.text_area("Enter text here:", height=200)
    if st.button("Analyze"):
        word_count = len(user_text.split())
        st.write(f"**Total Words:** {word_count}")
        sentences = user_text.split(". ")
        summary = ". ".join(sentences[:3]) + "." if len(sentences) > 3 else user_text
        st.subheader("📝 Summary:")
        st.write(summary)

# ------------------------ 🧮 Calculator ------------------------
elif page == "🧮 Calculator":
    st.title("🧮 Calculator App")
    col1, col2 = st.columns(2)
    with col1:
        num1 = st.number_input("Enter first number", value=0.0)
        num2 = st.number_input("Enter second number", value=0.0)
        operation = st.selectbox("Select operation", ["Addition", "Subtraction", "Multiplication", "Division"])
        if st.button("Calculate"):
            try:
                if operation == "Addition":
                    result = num1 + num2
                elif operation == "Subtraction":
                    result = num1 - num2
                elif operation == "Multiplication":
                    result = num1 * num2
                elif operation == "Division":
                    result = num1 / num2 if num2 != 0 else "Error! Division by zero."
                st.success(f"Result: {result}")
            except Exception as e:
                st.error(f"Calculation error: {e}")
    with col2:
        st.subheader("Scientific Calculator")
        sci_input = st.number_input("Enter number", value=0.0)
        sci_operation = st.selectbox("Select operation", ["Square", "Square Root", "Logarithm", "Sine", "Cosine", "Tangent"])
        if st.button("Compute"):
            try:
                if sci_operation == "Square":
                    sci_result = sci_input ** 2
                elif sci_operation == "Square Root":
                    sci_result = np.sqrt(sci_input)
                elif sci_operation == "Logarithm":
                    sci_result = np.log(sci_input) if sci_input > 0 else "Undefined"
                elif sci_operation == "Sine":
                    sci_result = np.sin(sci_input)
                elif sci_operation == "Cosine":
                    sci_result = np.cos(sci_input)
                elif sci_operation == "Tangent":
                    sci_result = np.tan(sci_input)
                st.success(f"Result: {sci_result}")
            except Exception as e:
                st.error(f"Computation error: {e}")

# Footer
st.sidebar.write("---")
st.sidebar.write("📌 Created by ❤️  **ASIF**")
