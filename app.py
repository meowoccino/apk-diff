import streamlit as st
import zipfile
import io
import re
import sqlite3
import tempfile
import ctypes
from PIL import Image
from groq import Groq

# Page Setup & Styling
st.set_page_config(page_title="APK Teardown Studio", page_icon="📱", layout="centered")

st.markdown("""
<style>
    /* Hide top header, toolbar, footer, and owner button */
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

    /* Force content to top of mobile screen */
    .main .block-container {
        padding-top: 0.2rem !important;
        padding-bottom: 2rem !important;
    }

    .stApp {
        background-color: #FEF7FF;
        color: #1D1B20;
        font-family: 'Roboto', sans-serif;
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
        margin-bottom: 12px;
    }
    
    /* Animated Pulse Card */
    .scanner-box {
        background: linear-gradient(135deg, #21005D 0%, #6750A4 100%);
        color: #FFFFFF;
        padding: 20px;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .pulse-ring {
        width: 40px;
        height: 40px;
        margin: 0 auto 12px auto;
        border: 4px solid #EADDFF;
        border-radius: 50%;
        animation: pulse 1.2s infinite ease-in-out;
    }
    @keyframes pulse {
        0% { transform: scale(0.8); opacity: 0.5; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(0.8); opacity: 0.5; }
    }
</style>
""", unsafe_allow_html=True)

# Session state management for Fullscreen Mode
if "report_html" not in st.session_state:
    st.session_state.report_html = None
if "added_image_keys" not in st.session_state:
    st.session_state.added_image_keys = []
if "new_data_images" not in st.session_state:
    st.session_state.new_data_images = {}

NOISE_PATTERNS = [
    "androidx/", "com/google/android/", "kotlin/", "java/", "javax/", 
    "android/support/", "org/apache/", "com/facebook/", "io/reactivex/",
    "Ljava/", "Lkotlin/", "Landroid/", "Landroidx/"
]

def is_framework_noise(token):
    token_lower = token.lower()
    return any(noise in token_lower for noise in NOISE_PATTERNS)

def demangle_cpp_symbol(mangled_str):
    """Attempts C++ symbol demangling using native C libraries if available."""
    try:
        for libname in ['libstdc++.so.6', 'libcxxabi.so.1', 'libc.so.6']:
            try:
                lib = ctypes.CDLL(libname)
                if hasattr(lib, '__cxa_demangle'):
                    cxa = lib.__cxa_demangle
                    cxa.restype = ctypes.c_char_p
                    res = cxa(mangled_str.encode('utf-8'), None, None, None)
                    if res:
                        return res.decode('utf-8', errors='ignore')
            except Exception:
                continue
    except Exception:
        pass
    return mangled_str

def inspect_sqlite_db(raw_bytes):
    """Scans asset databases (.db / .sqlite) and extracts table schemas."""
    schema_info = set()
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as tmp:
            tmp.write(raw_bytes)
            tmp.flush()
            conn = sqlite3.connect(tmp.name)
            cursor = conn.cursor()
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            for tbl, sql in tables[:15]:
                if tbl and not tbl.startswith("sqlite_"):
                    schema_info.add(f"Table: {tbl}")
            conn.close()
    except Exception:
        pass
    return schema_info

def check_xor_obfuscation(raw_bytes):
    """Sweeps for XOR-obfuscated HTTP endpoints."""
    found_urls = set()
    target = b"http"
    for key in range(1, 256):
        xored_target = bytes([b ^ key for b in target])
        if xored_target in raw_bytes:
            pos = raw_bytes.find(xored_target)
            chunk = raw_bytes[pos:pos+120]
            decoded_chunk = bytes([b ^ key for b in chunk])
            urls = re.findall(r'https?://[A-Za-z0-9_./\-]+', decoded_chunk.decode('ascii', errors='ignore'))
            for u in urls:
                if len(u) < 100:
                    found_urls.add(u)
            if len(found_urls) >= 8:
                break
    return found_urls

def extract_strings_from_bytes(raw_bytes):
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
    """Deep scans package files including databases, annotations, ProtoBufs, C++ symbols, and XOR sweeps."""
    details = {
        "files": set(),
        "total_size": 0,
        "all_strings": set(),
        "native_strings": set(),
        "config_strings": set(),
        "annotations": set(),
        "protobuf_schemas": set(),
        "db_schemas": set(),
        "xor_urls": set(),
        "activities": set(),
        "services": set(),
        "permissions": set(),
        "deep_links": set(),
        "endpoints": set(),
        "images": {}
    }
    
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            for name in z.namelist():
                info = z.getinfo(name)
                details["files"].add(name)
                details["total_size"] += info.file_size
                
                if name.endswith('/') or info.file_size == 0:
                    continue
                
                lower_name = name.lower()
                
                # Image asset capture
                if any(lower_name.endswith(ext) for ext in ['.png', '.webp', '.jpg']) and info.file_size < 300 * 1024:
                    if not any(ignore in lower_name for ignore in ["icon", "launcher", "splash"]):
                        try:
                            details["images"][name.split('/')[-1]] = z.read(name)
                        except Exception:
                            pass

                try:
                    raw_bytes = z.read(name) if info.file_size < 10 * 1024 * 1024 else z.open(name).read(5 * 1024 * 1024)
                    
                    # 1. SQLite Database Scan
                    if any(lower_name.endswith(ext) for ext in [".db", ".sqlite"]):
                        db_tables = inspect_sqlite_db(raw_bytes)
                        details["db_schemas"].update(db_tables)

                    # 2. ProtoBuf Schema Extraction
                    proto_matches = re.findall(rb'type\.googleapis\.com/[A-Za-z0-9_.-]+', raw_bytes)
                    for pm in proto_matches:
                        details["protobuf_schemas"].add(pm.decode('ascii', errors='ignore'))

                    # 3. XOR Obfuscated Endpoint Sweep
                    xor_found = check_xor_obfuscation(raw_bytes)
                    details["xor_urls"].update(xor_found)

                    file_tokens = extract_strings_from_bytes(raw_bytes)
                    
                    # 4. Native C++ Symbol Extraction & Demangling
                    if lower_name.endswith(".so"):
                        for token in file_tokens:
                            if token.startswith("_Z"):
                                demangled = demangle_cpp_symbol(token)
                                details["native_strings"].add(demangled)
                            else:
                                details["native_strings"].add(token)
                    elif any(lower_name.endswith(ext) for ext in [".csv", ".json", ".proto", ".txt", ".dat", ".xml", ".properties"]):
                        details["config_strings"].update(file_tokens)
                    else:
                        details["all_strings"].update(file_tokens)
                        
                    # 5. DEX Annotation & Model Mining
                    if lower_name.endswith(".dex"):
                        anno_matches = re.findall(rb'(?:SerializedName|Keep|Beta|Experimental|RequiresOptIn)[A-Za-z0-9_"\':\s]{2,60}', raw_bytes)
                        for am in anno_matches:
                            try:
                                details["annotations"].add(am.decode('ascii', errors='ignore').strip())
                            except Exception:
                                pass

                    # Categorize Android components
                    for token in file_tokens:
                        token_lower = token.lower()
                        if "permission." in token_lower:
                            details["permissions"].add(token)
                        elif "activity" in token_lower or "screen" in token_lower:
                            details["activities"].add(token)
                        elif "service" in token_lower or "receiver" in token_lower:
                            details["services"].add(token)
                        elif token_lower.startswith("http://") or token_lower.startswith("https://"):
                            details["endpoints"].add(token)
                        elif "scheme://" in token_lower or "://" in token_lower:
                            details["deep_links"].add(token)
                except Exception:
                    pass
                    
    except Exception as e:
        st.error(f"Error scanning package: {e}")
        
    return details

# ==================== FULLSCREEN REPORT VIEW ====================
if st.session_state.report_html:
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.markdown('<div class="title-text">📊 Deep Teardown Report</div>', unsafe_allow_html=True)
    with col_b:
        if st.button("↩️ Re-scan", use_container_width=True):
            st.session_state.report_html = None
            st.session_state.added_image_keys = []
            st.session_state.new_data_images = {}
            st.rerun()

    if st.session_state.added_image_keys:
        with st.expander("🖼️ View Added Visual Asset Previews", expanded=False):
            img_cols = st.columns(min(len(st.session_state.added_image_keys[:4]), 4))
            for idx, img_key in enumerate(st.session_state.added_image_keys[:4]):
                with img_cols[idx]:
                    try:
                        image = Image.open(io.BytesIO(st.session_state.new_data_images[img_key]))
                        st.image(image, caption=img_key[:15], width=70)
                    except Exception:
                        pass

    st.markdown(st.session_state.report_html, unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("📋 One-Tap Text Export")
    st.text_area(
        "Copy raw text below for Telegram, Reddit, or forum posts:", 
        value=re.sub('<[^<]+?>', '', st.session_state.report_html), 
        height=120
    )

# ==================== MAIN INPUT VIEW ====================
else:
    st.markdown('<div class="title-text">📱 Universal Deep APK Teardown</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-text">Deep-scans C++ demangled symbols, ProtoBufs, annotations, databases, and XOR secrets.</div>', unsafe_allow_html=True)

    custom_keywords = st.text_input(
        "🎯 Custom Search / Keyword Hunt (Optional):", 
        placeholder="e.g. dark_mode, season_2, pass, ai_tool, event"
    )

    col1, col2 = st.columns(2)
    with col1:
        old_file = st.file_uploader("Old Version (.apk / .aab)", type=["apk", "aab"])
    with col2:
        new_file = st.file_uploader("New Version (.apk / .aab)", type=["apk", "aab"])

    if st.button("🚀 Run Deep Package Teardown", type="primary", use_container_width=True):
        if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
            st.error("GROQ_API_KEY is missing from Streamlit Secrets!")
        elif not old_file or not new_file:
            st.error("Please upload both Old and New package files.")
        else:
            scanner_placeholder = st.empty()
            
            # Step 1: Scanner Animation
            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="pulse-ring"></div>
                <div style="font-weight: bold; font-size: 15px;">Scanning Package Archives & Native C++ Symbols...</div>
                <div style="font-size: 12px; opacity: 0.8; margin-top: 4px;">Demangling C++ libraries, parsing SQLite databases & ProtoBufs...</div>
            </div>
            """, unsafe_allow_html=True)
            
            old_bytes = old_file.read()
            new_bytes = new_file.read()
            
            old_data = inspect_entire_bundle(old_bytes)
            new_data = inspect_entire_bundle(new_bytes)
            
            # Step 2: Scanner Animation
            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="pulse-ring"></div>
                <div style="font-weight: bold; font-size: 15px;">Decoding Annotations & XOR Sweeps...</div>
                <div style="font-size: 12px; opacity: 0.8; margin-top: 4px;">Correlating unreleased flags, model annotations, and endpoints...</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Diffs Computation
            added_files = list(new_data["files"] - old_data["files"])
            removed_files = list(old_data["files"] - new_data["files"])
            
            added_native = list(new_data["native_strings"] - old_data["native_strings"])
            added_configs = list(new_data["config_strings"] - old_data["config_strings"])
            added_general = list(new_data["all_strings"] - old_data["all_strings"])
            
            added_annotations = list(new_data["annotations"] - old_data["annotations"])
            added_protobufs = list(new_data["protobuf_schemas"] - old_data["protobuf_schemas"])
            added_dbs = list(new_data["db_schemas"] - old_data["db_schemas"])
            added_xor = list(new_data["xor_urls"] - old_data["xor_urls"])
            
            added_activities = list(new_data["activities"] - old_data["activities"])
            added_services = list(new_data["services"] - old_data["services"])
            added_permissions = list(new_data["permissions"] - old_data["permissions"])
            added_deep_links = list(new_data["deep_links"] - old_data["deep_links"])
            added_endpoints = list(new_data["endpoints"] - old_data["endpoints"])
            
            st.session_state.added_image_keys = [k for k in new_data["images"].keys() if k not in old_data["images"]]
            st.session_state.new_data_images = new_data["images"]
            
            old_size_mb = round(old_data["total_size"] / (1024 * 1024), 2)
            new_size_mb = round(new_data["total_size"] / (1024 * 1024), 2)
            size_diff_mb = round(new_size_mb - old_size_mb, 2)
            
            combined_diffs = added_native + added_configs + added_general + added_annotations
            
            target_matches = []
            if custom_keywords.strip():
                user_terms = [t.strip().lower() for t in custom_keywords.split(",") if t.strip()]
                target_matches = [token for token in combined_diffs if any(term in token.lower() for term in user_terms)]

            feature_toggles = [t for t in combined_diffs if any(k in t.lower() for k in ['flag', 'enable', 'config', 'opt', 'toggle', 'experiment', 'beta'])]
            
            diff_summary = f"""
            OLD PACKAGE: {old_file.name} ({old_size_mb} MB)
            NEW PACKAGE: {new_file.name} ({new_size_mb} MB) | SIZE CHANGE: {size_diff_mb} MB
            
            === 1. TARGET KEYWORD MATCHES ({len(target_matches)}) ===
            {target_matches[:30]}
            
            === 2. FEATURE TOGGLES & DEX ANNOTATIONS ===
            FLAGS ({len(feature_toggles)}): {feature_toggles[:35]}
            ANNOTATIONS ({len(added_annotations)}): {added_annotations[:25]}
            
            === 3. DEMANGLED NATIVE C++ BINARY SYMBOLS (.so) ({len(added_native)}) ===
            {added_native[:35]}
            
            === 4. PROTOBUF SCHEMAS & DATABASE TABLES ===
            PROTOBUFS ({len(added_protobufs)}): {added_protobufs[:20]}
            DB TABLES ({len(added_dbs)}): {added_dbs[:20]}
            
            === 5. SERVER ENDPOINTS & DEEP LINKS ===
            ENDPOINTS ({len(added_endpoints)}): {added_endpoints[:20]}
            XOR DECODED ENDPOINTS ({len(added_xor)}): {added_xor[:15]}
            SCHEMES ({len(added_deep_links)}): {added_deep_links[:20]}
            
            === 6. NEW SCREENS & BACKGROUND SERVICES ===
            ACTIVITIES ({len(added_activities)}): {added_activities[:20]}
            SERVICES ({len(added_services)}): {added_services[:20]}
            PERMISSIONS ({len(added_permissions)}): {added_permissions[:15]}
            
            === 7. GAME CONFIGS & FILE PATH DIFFS ===
            CONFIGS ({len(added_configs)}): {added_configs[:30]}
            ADDED FILES ({len(added_files)}): {added_files[:20]}
            REMOVED FILES ({len(removed_files)}): {removed_files[:20]}
            """
            
            # Step 3: AI Query State Animation
            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="pulse-ring"></div>
                <div style="font-weight: bold; font-size: 15px;">Querying Groq AI Engine...</div>
                <div style="font-size: 12px; opacity: 0.8; margin-top: 4px;">Building Material Design 3 report dashboard...</div>
            </div>
            """, unsafe_allow_html=True)
            
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            
            prompt = f"""
            You are a lead tech journalist and mobile software investigator conducting a comprehensive APK/AAB Teardown.
            Examine the provided package diffs (including demangled C++ symbols, ProtoBuf schemas, SQLite tables, DEX annotations, and XOR endpoints).
            Format your response into a clean, modern Material Design 3 (MD3) report dashboard.

            Output strictly raw, clean HTML with inline CSS styled according to MD3 guidelines.
            Do NOT wrap your output in markdown codeblocks (do NOT use ```html or ```).
            
            Styling rules for modern dashboard cards:
            - Top Metric Chips Row: Display pills using `display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;` with background `#EADDFF` and color `#21005D`.
            - Accent Card Style: background-color: #F7F2FA; border-radius: 18px; padding: 16px; margin-bottom: 16px; border-left: 5px solid #6750A4; border-top: 1px solid #CAC4D0; border-right: 1px solid #CAC4D0; border-bottom: 1px solid #CAC4D0;
            - Spotlight Leak Card: background-color: #FFD8E4; color: #31111D; border-radius: 18px; padding: 16px; margin-bottom: 16px; border-left: 5px solid #B12B58;
            - Terminal / Command Blocks: background-color: #1D1B20; color: #E6E1E5; padding: 10px 14px; border-radius: 10px; font-family: monospace; font-size: 11px; word-break: break-all; margin-top: 8px; border-left: 3px solid #6750A4;
            
            Your report MUST include:
            1. **Top Metric Chips Row**: Highlighting Size Change, Impact Rating (e.g. 9/10), New Flags Count, and C++ Native Symbols Count.
            2. **Target Keyword Findings**: If custom keywords were found, detail them prominently at the top.
            3. **Executive Teardown Verdict**: Comprehensive synthesis explaining unreleased features, C++ architecture changes, and database modifications.
            4. **Unreleased Clues & Mobile Shell Commands**: Detail upcoming feature clues, followed by individual, copyable ADB shell commands inside dark terminal boxes (`adb shell device_config put...` or `adb shell am start...`).
            5. **Deep Technical Audits**: Highlight ProtoBuf schemas, XOR/server endpoints, new database tables, and permissions.

            RAW CATEGORIZED PACKAGE DIFF DATA:
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
                
                st.session_state.report_html = output_html
                scanner_placeholder.empty()
                st.rerun()
                
            except Exception as e:
                scanner_placeholder.empty()
                st.error(f"Groq API Error: {e}")
