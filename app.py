import streamlit as st
import zipfile
import io
import re
from groq import Groq

# Page Setup & Styling
st.set_page_config(page_title="APK Teardown AI", page_icon="🔍", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #FEF7FF; color: #1D1B20; }
    .title-text { font-size: 22px; font-weight: bold; color: #6750A4; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-text">📱 APK & Bundle Teardown AI</div>', unsafe_allow_html=True)
st.write("Compare two APK or AAB versions to uncover unreleased features, flags, and library updates.")

# Upload slots
col1, col2 = st.columns(2)
with col1:
    old_file = st.file_uploader("Old Version (.apk / .aab)", type=["apk", "aab"])
with col2:
    new_file = st.file_uploader("New Version (.apk / .aab)", type=["apk", "aab"])

def inspect_bundle(file_bytes):
    """Extracts file paths and readable text strings from APK/AAB ZIP packages."""
    details = {"files": set(), "strings": set()}
    with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
        for name in z.namelist():
            details["files"].add(name)
            if name.endswith(".xml") or "strings" in name:
                try:
                    raw_data = z.read(name).decode("utf-8", errors="ignore")
                    found_strings = re.findall(r'[A-Za-z0-9_]{5,}', raw_data)
                    details["strings"].update(found_strings[:200])
                except Exception:
                    pass
    return details

if st.button("Analyze & Compare", type="primary"):
    if "GROQ_API_KEY" not in st.secrets:
        st.error("GROQ_API_KEY is missing from Streamlit Secrets!")
    elif not old_file or not new_file:
        st.error("Please upload both old and new files.")
    else:
        with st.spinner("Extracting package diffs and asking Groq AI..."):
            # Compare both files
            old_data = inspect_bundle(old_file.read())
            new_data = inspect_bundle(new_file.read())
            
            added_files = list(new_data["files"] - old_data["files"])[:50]
            removed_files = list(old_data["files"] - new_data["files"])[:50]
            added_strings = list(new_data["strings"] - old_data["strings"])[:50]
            
            diff_summary = f"""
            OLD FILE: {old_file.name}
            NEW FILE: {new_file.name}
            
            ADDED FILES ({len(added_files)}): {added_files}
            REMOVED FILES ({len(removed_files)}): {removed_files}
            NEW STRINGS / KEYS ({len(added_strings)}): {added_strings}
            """
            
            # Connect to Groq using the secret key
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            
            prompt = f"""
            You are an expert Android tech reporter running an APK teardown.
            Analyze these package diffs and format your answer using clean HTML and Material Design 3 style concepts.
            
            Include:
            1. An Executive Summary verdict of what changed.
            2. An 'Unreleased Clues & Activation' section identifying potential unreleased features or flags, with copyable ADB commands (e.g., `adb shell device_config put...` or `adb shell am start...`).
            3. Added or removed libraries and asset cleanups.
            
            RAW DIFF DATA:
            {diff_summary}
            """
            
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            
            st.markdown(completion.choices[0].message.content, unsafe_allow_html=True)
