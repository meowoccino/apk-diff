import streamlit as st
import zipfile
import io
import re
from PIL import Image
from groq import Groq

# Page Setup & Styling
st.set_page_config(page_title="Universal APK Teardown Studio", page_icon="📱", layout="centered")

st.markdown("""
<style>
    /* Hide header, toolbar, footer, and developer overlays */
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

st.markdown('<div class="title-text">📱 Deep APK & Bundle Scanner</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Scans every file, folder, native library (.so), and game data config in the package.</div>', unsafe_allow_html=True)

# Mode Selector
analysis_mode = st.selectbox(
    "Select Teardown Focus:",
    [
        "📰 Tech Leaks & Unreleased Content (Features, Flags, Game Stats & Native C++)",
        "🛡️ Security & Privacy Audit (Permissions, Endpoints & Trackers)",
        "⚡ Code Architecture & Bloat (Native Libraries, Assets & Frameworks)"
    ]
)

# Upload Slots
col1, col2 = st.columns(2)
with col1:
    old_file = st.file_uploader("Old Version (.apk / .aab)", type=["apk", "aab"])
with col2:
    new_file = st.file_uploader("New Version (.apk / .aab)", type=["apk", "aab"])

# Common framework paths to ignore so real leaks stand out
NOISE_PATTERNS = [
    "androidx/", "com/google/android/", "kotlin/", "java/", "javax/", 
    "android/support/", "org/apache/", "com/facebook/", "io/reactivex/",
    "Ljava/", "Lkotlin/", "Landroid/", "Landroidx/"
]

def is_framework_noise(token):
    """Filters out standard framework noise to highlight actual app code."""
    token_lower = token.lower()
    return any(noise in token_lower for noise in NOISE_PATTERNS)

def extract_strings_from_bytes(raw_bytes):
    """Extracts clean printable ASCII and UTF-8 strings from any binary stream."""
    strings = set()
    matches = re.findall(rb'[\x20-\x7E]{5,}', raw_bytes)
    for m in matches:
        try:
            decoded = m.decode('ascii', errors='ignore').strip()
            if len(decoded) < 120 and not is_framework_noise(decoded):
                strings.add(decoded)
        except Exception:
            pass
    return strings

def inspect_entire_bundle(file_bytes):
    """Scans every single file and folder inside the uploaded archive."""
    details = {
        "files": set(),
        "total_size": 0,
        "all_strings": set(),
        "native_strings": set(),
        "config_strings": set(),
        "activities": set(),
        "permissions": set(),
        "deep_links": set(),
        "images": {}
    }
    
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            for name in z.namelist():
                info = z.getinfo(name)
                details["files"].add(name)
                details["total_size"] += info.file_size
                
                # Skip directory entries with 0 size
                if name.endswith('/') or info.file_size == 0:
                    continue
                
                lower_name = name.lower()
                
                # Capture preview images (under 300KB, ignoring standard launcher icons)
                if any(lower_name.endswith(ext) for ext in ['.png', '.webp', '.jpg']) and info.file_size < 300 * 1024:
                    if not any(ignore in lower_name for ignore in ["icon", "launcher", "splash"]):
                        try:
                            details["images"][name.split('/')[-1]] = z.read(name)
                        except Exception:
                            pass

                # Read up to 10MB per file to keep performance fast on mobile
                try:
                    raw_bytes = z.read(name) if info.file_size < 10 * 1024 * 1024 else z.open(name).read(5 * 1024 * 1024)
                    file_tokens = extract_strings_from_bytes(raw_bytes)
                    
                    # Categorize findings by file type
                    if lower_name.endswith(".so"):
                        details["native_strings"].update(file_tokens)
                    elif any(lower_name.endswith(ext) for ext in [".csv", ".json", ".proto", ".txt", ".dat", ".xml", ".properties"]):
                        details["config_strings"].update(file_tokens)
                    else:
                        details["all_strings"].update(file_tokens)
                        
                    # Filter components
                    for token in file_tokens:
                        if "permission." in token.lower():
                            details["permissions"].add(token)
                        elif "activity" in token.lower() or "screen" in token.lower():
                            details["activities"].add(token)
                        elif any(proto in token.lower() for proto in ["http://", "https://", "scheme://", "content://"]):
                            details["deep_links"].add(token)
                except Exception:
                    pass
                    
    except Exception as e:
        st.error(f"Error scanning package: {e}")
        
    return details

# Run Analysis
if st.button("🚀 Run Deep Package Teardown", type="primary", use_container_width=True):
    if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
        st.error("GROQ_API_KEY is missing from Streamlit Secrets!")
    elif not old_file or not new_file:
        st.error("Please upload both Old and New package files.")
    else:
        with st.spinner("Scanning every folder, C++ library (.so), and data config..."):
            old_bytes = old_file.read()
            new_bytes = new_file.read()
            
            old_data = inspect_entire_bundle(old_bytes)
            new_data = inspect_entire_bundle(new_bytes)
            
            # File diffs
            added_files = list(new_data["files"] - old_data["files"])
            removed_files = list(old_data["files"] - new_data["files"])
            
            # Data diffs across code, C++ binaries, and configs
            added_native = list(new_data["native_strings"] - old_data["native_strings"])
            added_configs = list(new_data["config_strings"] - old_data["config_strings"])
            added_general = list(new_data["all_strings"] - old_data["all_strings"])
            
            added_activities = list(new_data["activities"] - old_data["activities"])
            added_permissions = list(new_data["permissions"] - old_data["permissions"])
            added_deep_links = list(new_data["deep_links"] - old_data["deep_links"])
            
            added_image_keys = [k for k in new_data["images"].keys() if k not in old_data["images"]]
            
            old_size_mb = round(old_data["total_size"] / (1024 * 1024), 2)
            new_size_mb = round(new_data["total_size"] / (1024 * 1024), 2)
            size_diff_mb = round(new_size_mb - old_size_mb, 2)
            
            # Optional visual previews
            if added_image_keys:
                with st.expander("🖼️ Newly Added Asset Graphic Previews", expanded=False):
                    img_cols = st.columns(min(len(added_image_keys[:4]), 4))
                    for idx, img_key in enumerate(added_image_keys[:4]):
                        with img_cols[idx]:
                            try:
                                image = Image.open(io.BytesIO(new_data["images"][img_key]))
                                st.image(image, caption=img_key[:15], width=70)
                            except Exception:
                                pass

            # Prioritize potential leak keywords across all file sources
            combined_diffs = added_native + added_configs + added_general
            prioritized_tokens = sorted(
                combined_diffs, 
                key=lambda x: any(k in x.lower() for k in ['flag', 'enable', 'config', 'hero', 'troop', 'event', 'season', 'shop', 'v2', 'beta', 'opt']), 
                reverse=True
            )[:150]
            
            diff_summary = f"""
            OLD PACKAGE: {old_file.name} ({old_size_mb} MB)
            NEW PACKAGE: {new_file.name} ({new_size_mb} MB) | SIZE CHANGE: {size_diff_mb} MB
            FOCUS: {analysis_mode}
            
            NEW FILE PATHS ADDED ({len(added_files)}):
            {added_files[:40]}
            
            REMOVED FILE PATHS ({len(removed_files)}):
            {removed_files[:40]}
            
            NEW STRINGS FROM NATIVE C++ LIBRARIES (.so) ({len(added_native)}):
            {added_native[:40]}
            
            NEW STRINGS FROM GAME CONFIGS & DATA FILES ({len(added_configs)}):
            {added_configs[:40]}
            
            NEW SCREENS / ACTIVITIES ({len(added_activities)}):
            {added_activities[:20]}
            
            NEW PERMISSIONS ({len(added_permissions)}):
            {added_permissions[:15]}
            
            NEW DEEP LINKS / ROUTES ({len(added_deep_links)}):
            {added_deep_links[:15]}
            
            PRIORITIZED HIGH-SIGNAL LEAK TOKENS ({len(combined_diffs)} total diffs, top 150 shown):
            {prioritized_tokens}
            """
            
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            
            prompt = f"""
            You are a lead tech reporter and game data miner analyzing a complete APK/AAB package comparison.
            Review these package diffs (extracted from all files, C++ native libraries, bytecode, and data configs) based on the focus mode: '{analysis_mode}'.
            
            Output strictly raw, clean HTML with inline CSS styled according to Material Design 3 (MD3) guidelines.
            Do NOT wrap your output in markdown codeblocks (do NOT use ```html or ```).
            
            Styling rules:
            - Standard Cards: background-color: #F7F2FA; border-radius: 18px; padding: 16px; margin-bottom: 16px; border: 1px solid #CAC4D0;
            - Unreleased Spotlight Card: background-color: #FFD8E4; color: #31111D; border-radius: 20px; padding: 16px; margin-bottom: 16px;
            - AI Overview Card: background-color: #EADDFF; color: #21005D; border-radius: 18px; padding: 16px; margin-bottom: 16px;
            - Terminal / Command Blocks: background-color: #1D1B20; color: #E6E1E5; padding: 8px 12px; border-radius: 8px; font-family: monospace; font-size: 11px; word-break: break-all; margin-top: 6px;
            - Stat Badges: background-color: #CCE8E1; color: #05211B; font-weight: bold; padding: 4px 10px; border-radius: 100px; font-size: 11px; display: inline-block; margin-right: 4px;

            Your report MUST include:
            1. **Update Impact Rating (1 to 10)**: Significance rating at the top.
            2. **Diff Stat Badges**: Size change, new files, native C++ changes, and config token additions.
            3. **Executive Teardown Verdict**: Clear synthesis of what the developers or designers added.
            4. **Unreleased Clues & Activation Commands**: Connect new C++ symbols, config keys, and flags into feature predictions. Provide copyable shell activation commands (`adb shell device_config put...` or `adb shell am start...`).
            5. **Native C++ & Config Findings**: Highlight notable findings extracted specifically from `.so` libraries or game data tables.

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
