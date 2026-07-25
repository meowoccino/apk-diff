import streamlit as st
import zipfile
import io
import re
from groq import Groq

# Page Setup & Styling
st.set_page_config(page_title="APK Teardown Studio", page_icon="📱", layout="centered")

# Custom CSS: Hides default Streamlit header, footer, and branding
st.markdown("""
<style>
    header { visibility: hidden; height: 0px; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    div[data-testid="stDecoration"] { display: none; }
    div[data-testid="stHeader"] { display: none; }
    div[data-testid="stToolbar"] { display: none; }
    
    .stApp {
        background-color: #FEF7FF;
        color: #1D1B20;
        font-family: 'Roboto', sans-serif;
    }
    
    .title-text {
        font-size: 22px;
        font-weight: 700;
        color: #6750A4;
        margin-bottom: 4px;
    }
    
    .sub-text {
        font-size: 13px;
        color: #49454F;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# App Title Header
st.markdown('<div class="title-text">📱 APK & Bundle Teardown Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Compare two .apk or .aab files to uncover hidden feature flags, unreleased screens, SDK updates, and activation commands.</div>', unsafe_allow_html=True)

# File Upload Slots
col1, col2 = st.columns(2)
with col1:
    old_file = st.file_uploader("Old Version (.apk / .aab)", type=["apk", "aab"])
with col2:
    new_file = st.file_uploader("New Version (.apk / .aab)", type=["apk", "aab"])

def inspect_bundle(file_bytes):
    """Parses .apk or .aab ZIP structure and extracts file paths, sizes, and readable strings."""
    details = {"files": set(), "strings": set(), "total_size": 0}
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            for name in z.namelist():
                info = z.getinfo(name)
                details["files"].add(name)
                details["total_size"] += info.file_size
                
                # Extract plain text strings from XML, Manifests, and resource files
                if name.endswith(".xml") or "strings" in name or "manifest" in name.lower():
                    try:
                        raw_data = z.read(name).decode("utf-8", errors="ignore")
                        found_strings = re.findall(r'[A-Za-z0-9_]{5,}', raw_data)
                        details["strings"].update(found_strings[:300])
                    except Exception:
                        pass
    except Exception as e:
        st.error(f"Error processing package structure: {e}")
    return details

# Run Teardown Trigger
if st.button("🚀 Analyze & Compare", type="primary", use_container_width=True):
    if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
        st.error("GROQ_API_KEY is missing! Please add GROQ_API_KEY to your Streamlit Secrets.")
    elif not old_file or not new_file:
        st.error("Please upload both Old and New package files.")
    else:
        with st.spinner("Analyzing package diffs and generating teardown..."):
            # Extract contents from both uploaded archives
            old_bytes = old_file.read()
            new_bytes = new_file.read()
            
            old_data = inspect_bundle(old_bytes)
            new_data = inspect_bundle(new_bytes)
            
            # Compute package differences
            added_files = list(new_data["files"] - old_data["files"])
            removed_files = list(old_data["files"] - new_data["files"])
            added_strings = list(new_data["strings"] - old_data["strings"])
            
            old_size_mb = round(old_data["total_size"] / (1024 * 1024), 2)
            new_size_mb = round(new_data["total_size"] / (1024 * 1024), 2)
            size_diff_mb = round(new_size_mb - old_size_mb, 2)
            
            diff_summary = f"""
            OLD PACKAGE: {old_file.name} ({old_size_mb} MB)
            NEW PACKAGE: {new_file.name} ({new_size_mb} MB)
            SIZE DIFFERENCE: {size_diff_mb} MB
            
            ADDED FILE PATHS ({len(added_files)} total, showing top 60):
            {added_files[:60]}
            
            REMOVED FILE PATHS ({len(removed_files)} total, showing top 60):
            {removed_files[:60]}
            
            NEW STRINGS & KEY TOKENS ({len(added_strings)} total, showing top 60):
            {added_strings[:60]}
            """
            
            # Connect to Groq API using Secret Key
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            
            prompt = f"""
            You are an expert Android tech reporter conducting a detailed APK Teardown.
            Analyze the provided package diff data and produce a comprehensive teardown report.
            
            IMPORTANT: Output strictly raw, clean HTML (using inline CSS styles) formatted cleanly with Material Design 3 (MD3) styling concepts.
            Do NOT wrap your output in markdown codeblocks (do not use ```html or ```).
            
            Use these styling rules:
            - Standard Cards: background-color: #F7F2FA; border-radius: 18px; padding: 16px; margin-bottom: 16px; border: 1px solid #CAC4D0;
            - Unreleased Spotlight Card: background-color: #FFD8E4; color: #31111D; border-radius: 20px; padding: 16px; margin-bottom: 16px;
            - AI Overview Card: background-color: #EADDFF; color: #21005D; border-radius: 18px; padding: 16px; margin-bottom: 16px;
            - Terminal / Command Blocks: background-color: #1D1B20; color: #E6E1E5; padding: 8px 12px; border-radius: 8px; font-family: monospace; font-size: 11px; word-break: break-all; margin-top: 6px;
            - Stat Badges: background-color: #CCE8E1; color: #05211B; font-weight: bold; padding: 4px 10px; border-radius: 100px; font-size: 11px; display: inline-block; margin-right: 4px;
            
            Your report MUST include:
            1. **Diff Stat Pills**: Showing size change, added/removed files count, and string totals.
            2. **AI Teardown Summary**: An executive verdict detailing high-level updates.
            3. **Unreleased Clues & Activation Blueprints**: Uncover unreleased feature clues or hidden screens. For each feature/flag found, provide realistic manual activation shell commands (e.g., `adb shell device_config put...` or `adb shell am start...`).
            4. **Detailed Package Changes**: Categorized lists for New Strings, Removed SDKs/Assets, and Updated Frameworks.
            5. **Size Bloat Breakdown**: Visual summary of where the extra size was added.

            RAW PACKAGE DIFF DATA:
            {diff_summary}
            """
            
            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                
                output_html = completion.choices[0].message.content
                
                # Sanitize markdown wrappers if present
                output_html = re.sub(r"^```html\s*", "", output_html, flags=re.MULTILINE)
                output_html = re.sub(r"^```\s*", "", output_html, flags=re.MULTILINE)
                
                st.markdown(output_html, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Groq API Processing Error: {e}")
