import streamlit as st
import zipfile
import io
import re
from PIL import Image
from groq import Groq

# Page Setup & Clean Styling
st.set_page_config(page_title="APK Teardown Studio", page_icon="📱", layout="centered")

st.markdown("""
<style>
    /* Hide top header, toolbar, footer, and owner "Manage App" floating button */
    [data-testid="stHeader"], 
    [data-testid="stToolbar"], 
    [data-testid="stDecoration"], 
    [data-testid="stStatusWidget"],
    [data-testid="manage-app-button"],
    header, 
    footer, 
    .viewerBadge_container__1QSob,
    .styles_viewerBadge__1yB5_ {
        display: none !important;
        height: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
    }

    /* Remove empty padding at the top of mobile screens */
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }

    .stApp {
        background-color: #FEF7FF;
        color: #1D1B20;
    }
    
    .title-text {
        font-size: 22px;
        font-weight: 700;
        color: #6750A4;
        margin-bottom: 2px;
    }
    .sub-text {
        font-size: 13px;
        color: #49454F;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title-text">📱 Universal APK & Bundle Teardown</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Deep binary & game file scanner: Uncovers unreleased features, game stats, flags, and deep links.</div>', unsafe_allow_html=True)

# Mode Selector
analysis_mode = st.selectbox(
    "Select Teardown Focus:",
    [
        "📰 Tech & Leaks Reporter Mode (Features, Game Stats & Unreleased Content)",
        "🛡️ Security & Privacy Mode (Permissions, Trackers & Access)",
        "⚡ Performance & Code Mode (Size Bloat, Libraries & Assets)"
    ]
)

# Upload Slots
col1, col2 = st.columns(2)
with col1:
    old_file = st.file_uploader("Old Version (.apk / .aab)", type=["apk", "aab"])
with col2:
    new_file = st.file_uploader("New Version (.apk / .aab)", type=["apk", "aab"])

def extract_binary_strings(raw_bytes):
    """Extracts printable strings from DEX bytecode, XMLs, JSONs, CSVs, and binary configs."""
    extracted = set()
    
    # ASCII / UTF-8 printable characters
    ascii_matches = re.findall(rb'[\x20-\x7E]{5,}', raw_bytes)
    for m in ascii_matches:
        try:
            decoded = m.decode('ascii', errors='ignore').strip()
            if len(decoded) < 100:
                extracted.add(decoded)
        except Exception:
            pass
            
    return extracted

def inspect_bundle(file_bytes):
    """Deep inspects APK/AAB packages, scanning code, game data files, and assets."""
    details = {
        "files": set(),
        "total_size": 0,
        "strings": set(),
        "activities": set(),
        "permissions": set(),
        "deep_links": set(),
        "game_configs": set(),
        "images": {}
    }
    
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            for name in z.namelist():
                info = z.getinfo(name)
                details["files"].add(name)
                details["total_size"] += info.file_size
                lower_name = name.lower()
                
                # Capture small asset images (excluding huge launcher icons)
                if any(lower_name.endswith(ext) for ext in ['.png', '.webp', '.jpg']) and info.file_size < 300 * 1024:
                    if not any(ignore in lower_name for ignore in ["icon", "launcher", "splash", "background"]):
                        try:
                            details["images"][name.split('/')[-1]] = z.read(name)
                        except Exception:
                            pass

                # Deep scan code, binary XMLs, game CSVs, JSONs, and text configs
                if any(lower_name.endswith(ext) for ext in [".dex", ".xml", ".arsc", ".json", ".csv", ".txt", ".proto", ".properties"]):
                    try:
                        raw_bytes = z.read(name)
                        tokens = extract_binary_strings(raw_bytes)
                        
                        if any(ext in lower_name for ext in [".csv", ".json", ".proto"]):
                            details["game_configs"].add(name.split('/')[-1])
                            
                        for token in tokens:
                            details["strings"].add(token)
                            
                            if "permission." in token.lower():
                                details["permissions"].add(token)
                            elif "activity" in token.lower() or "screen" in token.lower():
                                details["activities"].add(token)
                            elif any(proto in token.lower() for proto in ["http://", "https://", "scheme://"]):
                                details["deep_links"].add(token)
                    except Exception:
                        pass
    except Exception as e:
        st.error(f"Error reading package archive: {e}")
        
    return details

# Run Analysis
if st.button("🚀 Analyze & Generate Teardown", type="primary", use_container_width=True):
    if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
        st.error("GROQ_API_KEY is missing from Streamlit Secrets!")
    elif not old_file or not new_file:
        st.error("Please upload both Old and New package files.")
    else:
        with st.spinner("Decoding binary code & game config files..."):
            old_bytes = old_file.read()
            new_bytes = new_file.read()
            
            old_data = inspect_bundle(old_bytes)
            new_data = inspect_bundle(new_bytes)
            
            # Package diffs
            added_files = list(new_data["files"] - old_data["files"])
            removed_files = list(old_data["files"] - new_data["files"])
            added_strings = list(new_data["strings"] - old_data["strings"])
            added_activities = list(new_data["activities"] - old_data["activities"])
            added_permissions = list(new_data["permissions"] - old_data["permissions"])
            added_deep_links = list(new_data["deep_links"] - old_data["deep_links"])
            added_configs = list(new_data["game_configs"] - old_data["game_configs"])
            
            added_image_keys = [k for k in new_data["images"].keys() if k not in old_data["images"]]
            
            old_size_mb = round(old_data["total_size"] / (1024 * 1024), 2)
            new_size_mb = round(new_data["total_size"] / (1024 * 1024), 2)
            size_diff_mb = round(new_size_mb - old_size_mb, 2)
            
            # Optional image preview in a compact expander
            if added_image_keys:
                with st.expander("🖼️ View Added Graphic Assets (Optional)", expanded=False):
                    img_cols = st.columns(min(len(added_image_keys[:4]), 4))
                    for idx, img_key in enumerate(added_image_keys[:4]):
                        with img_cols[idx]:
                            try:
                                image = Image.open(io.BytesIO(new_data["images"][img_key]))
                                st.image(image, caption=img_key[:15], width=70)
                            except Exception:
                                pass

            # Prioritize leak keywords
            prioritized_tokens = sorted(
                added_strings, 
                key=lambda x: any(k in x.lower() for k in ['flag', 'enable', 'config', 'troop', 'hero', 'level', 'event', 'season', 'shop', 'offer', 'beta']), 
                reverse=True
            )[:120]
            
            diff_summary = f"""
            OLD PACKAGE: {old_file.name} ({old_size_mb} MB)
            NEW PACKAGE: {new_file.name} ({new_size_mb} MB) | SIZE CHANGE: {size_diff_mb} MB
            SELECTED FOCUS: {analysis_mode}
            
            CHANGED/ADDED GAME DATA CONFIG FILES ({len(added_configs)}):
            {added_configs[:20]}
            
            NEWLY ADDED SCREENS / ACTIVITIES ({len(added_activities)}):
            {added_activities[:25]}
            
            NEWLY ADDED PERMISSIONS ({len(added_permissions)}):
            {added_permissions[:15]}
            
            NEWLY ADDED DEEP LINKS / ROUTES ({len(added_deep_links)}):
            {added_deep_links[:15]}
            
            NEW INTERNAL TOKENS & GAME STRINGS ({len(added_strings)} total, top 120 shown):
            {prioritized_tokens}
            """
            
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            
            prompt = f"""
            You are an expert tech investigator and game data miner conducting an APK/AAB Teardown.
            Examine these package diffs according to the requested focus mode: '{analysis_mode}'.
            
            Output strictly raw, clean HTML with inline CSS styled according to Material Design 3 (MD3) guidelines.
            Do NOT wrap your output in markdown codeblocks (do NOT use ```html or ```).
            
            Styling rules:
            - Standard Cards: background-color: #F7F2FA; border-radius: 18px; padding: 16px; margin-bottom: 16px; border: 1px solid #CAC4D0;
            - Unreleased Spotlight Card: background-color: #FFD8E4; color: #31111D; border-radius: 20px; padding: 16px; margin-bottom: 16px;
            - AI Overview Card: background-color: #EADDFF; color: #21005D; border-radius: 18px; padding: 16px; margin-bottom: 16px;
            - Terminal / Command Blocks: background-color: #1D1B20; color: #E6E1E5; padding: 8px 12px; border-radius: 8px; font-family: monospace; font-size: 11px; word-break: break-all; margin-top: 6px;
            - Stat Badges: background-color: #CCE8E1; color: #05211B; font-weight: bold; padding: 4px 10px; border-radius: 100px; font-size: 11px; display: inline-block; margin-right: 4px;

            Your report MUST include:
            1. **Update Impact Rating (1 to 10)**: An overall significance badge at the top (e.g., "Impact Rating: 8/10 - Major Feature/Event Update").
            2. **Diff Stat Pills**: Size change, new tokens count, changed game data files, and file diff totals.
            3. **Executive Teardown Verdict**: Synthesize what the developers or game designers are preparing.
            4. **Unreleased Clues & Activation Commands**: Connect new strings, tokens, and config changes into unreleased feature or game content predictions. Include copyable shell commands (`adb shell device_config put...` or `adb shell am start...`).
            5. **Deep Link Routes & Permissions**: Highlight new URL schemes or sensitive permissions if present.

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
                output_html = re.sub(r"^```html\s*", "", output_html, flags=re.MULTILINE)
                output_html = re.sub(r"^```\s*", "", output_html, flags=re.MULTILINE)
                
                st.markdown(output_html, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Groq API Error: {e}")
