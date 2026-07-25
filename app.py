import streamlit as st
import zipfile
import io
import re
import google.generativeai as genai

# Page Configuration
st.set_page_config(page_title="APK Teardown AI", page_icon="🔍", layout="centered")

# Custom MD3 Styling Injection
st.markdown("""
<style>
    .stApp { background-color: #FEF7FF; color: #1D1B20; }
    .card { background-color: #F7F2FA; border-radius: 18px; padding: 16px; border: 1px solid #CAC4D0; margin-bottom: 16px; }
    .title-text { font-size: 20px; font-weight: bold; color: #6750A4; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-text">📱 APK & Bundle Teardown AI</div>', unsafe_allow_html=True)
st.write("Compare two APK or AAB bundle versions to uncover changes, unreleased features, and flag commands.")

# API Key Input
api_key = st.text_input("Enter Google Gemini API Key:", type="password")

# File Uploaders
col1, col2 = st.columns(2)
with col1:
    old_file = st.file_uploader("Old Version (.apk / .aab)", type=["apk", "aab"])
with col2:
    new_file = st.file_uploader("New Version (.apk / .aab)", type=["apk", "aab"])

def inspect_bundle(file_bytes):
    """Extracts file structures, assets, and readable text strings from APK/AAB ZIP packages."""
    details = {"files": set(), "strings": set(), "sizes": {}}
    with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
        for name in z.namelist():
            details["files"].add(name)
            details["sizes"][name] = z.getinfo(name).file_size
            
            # Extract plain text strings from XML/resources where readable
            if name.endswith(".xml") or "strings" in name:
                try:
                    raw_data = z.read(name).decode("utf-8", errors="ignore")
                    found_strings = re.findall(r'[A-Za-z0-9_]{5,}', raw_data)
                    details["strings"].update(found_strings[:200])
                except Exception:
                    pass
    return details

if st.button("Analyze & Compare", type="primary"):
    if not api_key:
        st.error("Please enter your Gemini API key first.")
    elif not old_file or not new_file:
        st.error("Please upload both old and new files.")
    else:
        with st.spinner("Parsing APK structure and running AI teardown..."):
            # Inspect both files
            old_data = inspect_bundle(old_file.read())
            new_data = inspect_bundle(new_file.read())
            
            # Calculate raw diffs
            added_files = list(new_data["files"] - old_data["files"])[:50]
            removed_files = list(old_data["files"] - new_data["files"])[:50]
            added_strings = list(new_data["strings"] - old_data["strings"])[:50]
            
            diff_summary = f"""
            OLD FILE: {old_file.name}
            NEW FILE: {new_file.name}
            
            ADDED FILES/PATHS ({len(added_files)} shown):
            {added_files}
            
            REMOVED FILES/PATHS ({len(removed_files)} shown):
            {removed_files}
            
            NEW STRINGS / FEATURE KEYS ({len(added_strings)} shown):
            {added_strings}
            """
            
            # Prompt Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            prompt = f"""
            You are an expert Android news investigator conducting an APK Teardown.
            Analyze these package diffs and format your response in clean HTML using Material Design 3 styling concepts.
            
            Include:
            1. An Executive Summary verdict of what changed.
            2. An 'Unreleased Clues & Activation' section identifying potential upcoming features or flags, complete with copyable ADB commands (e.g. `adb shell device_config put...` or `adb shell am start...`).
            3. A breakdown of added/removed libraries and assets.
            
            RAW DIFF DATA:
            {diff_summary}
            """
            
            response = model.generate_content(prompt)
            st.markdown(response.text, unsafe_allow_html=True)
