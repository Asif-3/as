import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import PyPDF2
import pytesseract
from PIL import Image
import json

# Ensure required dependencies are installed
try:
    import openpyxl
except ImportError:
    st.error("Missing optional dependency 'openpyxl'. Use pip or conda to install openpyxl.")

# Set Page Configuration
st.set_page_config(page_title="Advanced Web Portal", page_icon="🚀", layout="wide")

# Sidebar - Navigation
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["📝 Notes App", "📊 Data Visualizer", "📂 File Uploader", "🔢 Text Analyzer", "🧮 Calculator"])

# Function to Save Uploaded Files
def save_uploaded_file(uploaded_file):
    folder = "uploaded_files"
    if not os.path.exists(folder):
        os.makedirs(folder)
    file_path = os.path.join(folder, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

# ------------------------ 📝 Notes App ------------------------
if page == "📝 Notes App":
    st.title("📝 Notes App")
    notes_file = "notes.txt"
    note = st.text_area("Write your note:", height=150)
    if st.button("Save Note"):
        with open(notes_file, "a") as file:
            file.write(note + "\n" + "-"*40 + "\n")
        st.success("Note saved!")
    if os.path.exists(notes_file):
        with open(notes_file, "r") as file:
            st.subheader("📜 Your Saved Notes:")
            st.text(file.read())

# ------------------------ 📊 Data Visualizer ------------------------
elif page == "📊 Data Visualizer":
    st.title("📊 Data Visualization Dashboard")
    uploaded_file = st.file_uploader("Upload File", type=None)
    if uploaded_file is not None:
        file_path = save_uploaded_file(uploaded_file)
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(file_path)
            elif uploaded_file.name.endswith(".xlsx"):
                df = pd.read_excel(file_path, engine='openpyxl')
            elif uploaded_file.name.endswith(".json"):
                df = pd.read_json(file_path)
            else:
                df = None
            
            if df is not None:
                st.dataframe(df.head())
        except Exception as e:
            st.error(f"Error processing file: {e}")

# ------------------------ 📂 File Uploader ------------------------
elif page == "📂 File Uploader":
    st.title("📂 File Uploader & Viewer")
    uploaded_file = st.file_uploader("Upload any file", type=None)
    if uploaded_file is not None:
        file_path = save_uploaded_file(uploaded_file)
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
            result = eval(f"{num1} {operation[0]} {num2}") if operation != "Division" or num2 != 0 else "Error! Division by zero."
            st.success(f"Result: {result}")
    with col2:
        st.subheader("Scientific Calculator")
        sci_input = st.number_input("Enter number", value=0.0)
        sci_operation = st.selectbox("Select operation", ["Square", "Square Root", "Logarithm", "Sine", "Cosine", "Tangent"])
        if st.button("Compute"):
            sci_result = eval(f"np.{sci_operation.lower()}(sci_input)")
            st.success(f"Result: {sci_result}")

st.sidebar.write("---")
st.sidebar.write("📌 Created by ❤️  **ASIF**")
