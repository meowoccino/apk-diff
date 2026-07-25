import streamlit as st
import zipfile
import io
import re
import sqlite3
import tempfile
import ctypes
from PIL import Image
from groq import Groq

# Page Setup
st.set_page_config(page_title="APK Teardown Studio", page_icon="⚡", layout="centered")

# Material Design 3 Styling
st.markdown("""
<style>
    /* Completely hide top header, toolbar, footer, and owner overlay buttons */
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

    /* Force content to start right at the top of mobile screens */
    .main .block-container {
        padding-top: 0rem !important;
        margin-top: 0rem !important;
        padding-bottom: 2rem !important;
        max-width: 500px !important;
    }

    /* Global Surface Palette */
    .stApp {
        background-color: #FEF7FF;
        color: #1D1B20;
        font-family: 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Modern Hero Header Container */
    .hero-card {
        background-color: #F3EDF7;
        border: 1px solid #E7E0EC;
        border-radius: 20px;
        padding: 16px 16px;
        margin-top: 4px;
        margin-bottom: 12px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.03);
    }

    .hero-title-row {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 4px;
    }

    .icon-badge {
        background-color: #EADDFF;
        color: #21005D;
        width: 38px;
        height: 38px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .hero-title {
        font-size: 19px;
        font-weight: 700;
        color: #1D1B20;
        line-height: 1.2;
    }

    .hero-sub {
        font-size: 12px;
        color: #49454F;
        line-height: 1.4;
        margin-top: 2px;
    }

    /* File Uploaders */
    div[data-testid="stFileUploader"] {
        background-color: #F3EDF7 !important;
        border: 1px dashed #938F99 !important;
        border-radius: 16px !important;
        padding: 6px !important;
    }

    /* Primary MD3 Button */
    div.stButton > button {
        background: #6750A4 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 100px !important;
        padding: 12px 20px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 6px rgba(103, 80, 164, 0.25) !important;
        transition: all 0.2s ease-in-out !important;
        margin-top: 6px;
    }

    div.stButton > button:hover, div.stButton > button:active {
        background: #503E81 !important;
        transform: translateY(-1px) !important;
    }

    /* Scanner Animation Card */
    .scanner-box {
        background: linear-gradient(135deg, #21005D 0%, #6750A4 100%);
        color: #FFFFFF;
        padding: 20px 16px;
        border-radius: 20px;
        text-align: center;
        margin-top: 10px;
        margin-bottom: 16px;
    }

    .pulse-ring {
        width: 36px;
        height: 36px;
        margin: 0 auto 10px auto;
        border: 3px solid #EADDFF;
        border-radius: 50%;
        animation: pulse 1.2s infinite ease-in-out;
    }

    @keyframes pulse {
        0% { transform: scale(0.85); opacity: 0.6; }
        50% { transform: scale(1.1); opacity: 1; }
        100% { transform: scale(0.85); opacity: 0.6; }
    }
</style>
""", unsafe_allow_html=True)

# Session state management
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
    """Attempts C++ symbol demangling using native C libraries."""
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

def process_zip_archive(zip_obj, details):
    """Processes any ZIP archive (APK, AAB, or split container)."""
    for name in zip_obj.namelist():
        info = zip_obj.getinfo(name)
        
        if name.endswith('.apk') and name != zip_obj.filename:
            try:
                sub_apk_bytes = zip_obj.read(name)
                with zipfile.ZipFile(io.BytesIO(sub_apk_bytes), "r") as sub_z:
                    process_zip_archive(sub_z, details)
            except Exception:
                pass
            continue

        details["files"].add(name)
        details["total_size"] += info.file_size
        
        if name.endswith('/') or info.file_size == 0:
            continue
        
        lower_name = name.lower()
        
        if any(lower_name.endswith(ext) for ext in ['.png', '.webp', '.jpg']) and info.file_size < 300 * 1024:
            if not any(ignore in lower_name for ignore in ["icon", "launcher", "splash"]):
                try:
                    details["images"][name.split('/')[-1]] = zip_obj.read(name)
                except Exception:
                    pass

        try:
            raw_bytes = zip_obj.read(name) if info.file_size < 10 * 1024 * 1024 else zip_obj.open(name).read(5 * 1024 * 1024)
            
            if any(lower_name.endswith(ext) for ext in [".db", ".sqlite"]):
                db_tables = inspect_sqlite_db(raw_bytes)
                details["db_schemas"].update(db_tables)

            proto_matches = re.findall(rb'type\.googleapis\.com/[A-Za-z0-9_.-]+', raw_bytes)
            for pm in proto_matches:
                details["protobuf_schemas"].add(pm.decode('ascii', errors='ignore'))

            graphql_matches = re.findall(rb'(?:query|mutation)\s+[A-Za-z0-9_]+', raw_bytes)
            for gqm in graphql_matches:
                details["graphql_ops"].add(gqm.decode('ascii', errors='ignore'))

            jni_matches = re.findall(rb'Java_[A-Za-z0-9_]+', raw_bytes)
            for jm in jni_matches:
                details["jni_exports"].add(jm.decode('ascii', errors='ignore'))

            if lower_name.endswith(".dex"):
                class_matches = re.findall(rb'L[a-zA-Z0-9_$]+/[a-zA-Z0-9_$]+;', raw_bytes)
                for cm in class_matches[:100]:
                    decoded_cls = cm.decode('ascii', errors='ignore')
                    if not is_framework_noise(decoded_cls):
                        details["class_paths"].add(decoded_cls)

                anno_matches = re.findall(rb'(?:SerializedName|Keep|Beta|Experimental|RequiresOptIn)[A-Za-z0-9_"\':\s]{2,60}', raw_bytes)
                for am in anno_matches:
                    try:
                        details["annotations"].add(am.decode('ascii', errors='ignore').strip())
                    except Exception:
                        pass

            xor_found = check_xor_obfuscation(raw_bytes)
            details["xor_urls"].update(xor_found)

            file_tokens = extract_strings_from_bytes(raw_bytes)
            
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

def inspect_entire_bundle(file_bytes):
    """Master entry point for processing APKs, AABs, XAPKs, APKS, and ZIPs."""
    details = {
        "files": set(),
        "total_size": 0,
        "all_strings": set(),
        "native_strings": set(),
        "config_strings": set(),
        "annotations": set(),
        "protobuf_schemas": set(),
        "graphql_ops": set(),
        "jni_exports": set(),
        "class_paths": set(),
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
            process_zip_archive(z, details)
    except Exception as e:
        st.error(f"Error reading package bundle: {e}")
        
    return details

# ==================== FULLSCREEN REPORT VIEW ====================
if st.session_state.report_html:
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.markdown("""
        <div style="font-size: 19px; font-weight: 700; color: #1D1B20; margin-top: 4px;">Deep Teardown Report</div>
        """, unsafe_allow_html=True)
    with col_b:
        if st.button("↩️ Re-scan", use_container_width=True):
            st.session_state.report_html = None
            st.session_state.added_image_keys = []
            st.session_state.new_data_images = {}
            st.rerun()

    if st.session_state.added_image_keys:
        with st.expander("View Added Graphic Previews", expanded=False):
            img_cols = st.columns(min(len(st.session_state.added_image_keys[:4]), 4))
            for idx, img_key in enumerate(st.session_state.added_image_keys[:4]):
                with img_cols[idx]:
                    try:
                        image = Image.open(io.BytesIO(st.session_state.new_data_images[img_key]))
                        st.image(image, caption=img_key[:15], width=70)
                    except Exception:
                        pass

    st.markdown(st.session_state.report_html, unsafe_allow_html=True)

# ==================== MAIN INPUT VIEW ====================
else:
    # Modern Vector Header Component
    st.markdown("""
    <div class="hero-card">
        <div class="hero-title-row">
            <div class="icon-badge">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#21005D" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="5" y="2" width="14" height="20" rx="3" ry="3"></rect>
                    <line x1="12" y1="18" x2="12.01" y2="18"></line>
                    <path d="M9 6h6"></path>
                </svg>
            </div>
            <div class="hero-title">APK Teardown Studio</div>
        </div>
        <div class="hero-sub">Scans C++ JNI exports, GraphQL, ProtoBufs, DEX class diffs, databases, and split bundles.</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        old_file = st.file_uploader("Old Version (.apk, .aab, .xapk, .apks)", type=["apk", "aab", "xapk", "apks", "zip"])
    with col2:
        new_file = st.file_uploader("New Version (.apk, .aab, .xapk, .apks)", type=["apk", "aab", "xapk", "apks", "zip"])

    if st.button("Run Deep Package Teardown", type="primary", use_container_width=True):
        if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
            st.error("GROQ_API_KEY is missing from Streamlit Secrets!")
        elif not old_file or not new_file:
            st.error("Please upload both Old and New package files.")
        else:
            scanner_placeholder = st.empty()
            
            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="pulse-ring"></div>
                <div style="font-weight: 700; font-size: 15px;">Parsing Archives & Native JNI Bridges...</div>
                <div style="font-size: 12px; opacity: 0.85; margin-top: 4px;">Demangling C++ symbols, mapping GraphQL queries & ProtoBufs...</div>
            </div>
            """, unsafe_allow_html=True)
            
            old_bytes = old_file.read()
            new_bytes = new_file.read()
            
            old_data = inspect_entire_bundle(old_bytes)
            new_data = inspect_entire_bundle(new_bytes)
            
            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="pulse-ring"></div>
                <div style="font-weight: 700; font-size: 15px;">Diffing Bytecode Classes & XOR Sweeps...</div>
                <div style="font-size: 12px; opacity: 0.85; margin-top: 4px;">Correlating unreleased flags, annotations, and database tables...</div>
            </div>
            """, unsafe_allow_html=True)
            
            added_files = list(new_data["files"] - old_data["files"])
            removed_files = list(old_data["files"] - new_data["files"])
            
            added_native = list(new_data["native_strings"] - old_data["native_strings"])
            added_configs = list(new_data["config_strings"] - old_data["config_strings"])
            added_general = list(new_data["all_strings"] - old_data["all_strings"])
            
            added_annotations = list(new_data["annotations"] - old_data["annotations"])
            added_protobufs = list(new_data["protobuf_schemas"] - old_data["protobuf_schemas"])
            added_graphql = list(new_data["graphql_ops"] - old_data["graphql_ops"])
            added_jni = list(new_data["jni_exports"] - old_data["jni_exports"])
            added_classes = list(new_data["class_paths"] - old_data["class_paths"])
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
            
            combined_diffs = added_native + added_configs + added_general + added_annotations + added_jni
            feature_toggles = [t for t in combined_diffs if any(k in t.lower() for k in ['flag', 'enable', 'config', 'opt', 'toggle', 'experiment', 'beta'])]
            
            diff_summary = f"""
            OLD PACKAGE: {old_file.name} ({old_size_mb} MB)
            NEW PACKAGE: {new_file.name} ({new_size_mb} MB) | SIZE CHANGE: {size_diff_mb} MB
            
            === 1. FEATURE TOGGLES & ANNOTATIONS ===
            FLAGS ({len(feature_toggles)}): {feature_toggles[:30]}
            ANNOTATIONS ({len(added_annotations)}): {added_annotations[:20]}
            
            === 2. JNI NATIVE C++ BRIDGES & SYMBOLS ===
            JNI EXPORTS ({len(added_jni)}): {added_jni[:25]}
            DEMANGLED C++ SYMBOLS ({len(added_native)}): {added_native[:30]}
            
            === 3. GRAPHQL, PROTOBUFS & DATABASES ===
            GRAPHQL QUERIES ({len(added_graphql)}): {added_graphql[:20]}
            PROTOBUFS ({len(added_protobufs)}): {added_protobufs[:20]}
            DB TABLES ({len(added_dbs)}): {added_dbs[:15]}
            
            === 4. BYTECODE CLASS HIERARCHY DIFFS ({len(added_classes)}) ===
            {added_classes[:30]}
            
            === 5. SERVER ENDPOINTS & DEEP LINKS ===
            ENDPOINTS ({len(added_endpoints)}): {added_endpoints[:20]}
            XOR DECODED ENDPOINTS ({len(added_xor)}): {added_xor[:15]}
            SCHEMES ({len(added_deep_links)}): {added_deep_links[:20]}
            
            === 6. NEW SCREENS & BACKGROUND SERVICES ===
            ACTIVITIES ({len(added_activities)}): {added_activities[:20]}
            SERVICES ({len(added_services)}): {added_services[:20]}
            PERMISSIONS ({len(added_permissions)}): {added_permissions[:15]}
            
            === 7. FILE PATH DIFFS ===
            ADDED FILES ({len(added_files)}): {added_files[:20]}
            REMOVED FILES ({len(removed_files)}): {removed_files[:20]}
            """
            
            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="pulse-ring"></div>
                <div style="font-weight: 700; font-size: 15px;">Querying Groq AI Engine...</div>
                <div style="font-size: 12px; opacity: 0.85; margin-top: 4px;">Building Material Design 3 report dashboard...</div>
            </div>
            """, unsafe_allow_html=True)
            
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            
            prompt = f"""
            You are a lead tech journalist conducting a complete APK/AAB Teardown.
            Analyze these package diffs and format your response into a clean, modern Material Design 3 (MD3) dashboard.

            Output strictly raw, clean HTML with inline CSS. Do NOT wrap in markdown codeblocks (do NOT use ```html or ```).
            
            Styling rules:
            - Metric Pills Row: flex gap:6px, flex-wrap, margin-bottom:12px. Pills use background `#EADDFF`, text `#21005D`, padding `4px 10px`, border-radius `100px`, font-size `11px`, font-weight `bold`.
            - AI Summary Card: background-color: #EADDFF; color: #21005D; border-radius: 16px; padding: 14px; margin-bottom: 12px; border-left: 4px solid #6750A4;
            - Unreleased Blueprint Card: background-color: #FFD8E4; color: #31111D; border-radius: 16px; padding: 14px; margin-bottom: 12px; border-left: 4px solid #B12B58;
            - Raw Package Changes Card: background-color: #F7F2FA; color: #1D1B20; border-radius: 16px; padding: 14px; margin-bottom: 12px; border: 1px solid #CAC4D0; border-left: 4px solid #79747E;
            - Terminal / Command Blocks: background-color: #1D1B20; color: #E6E1E5; padding: 8px 12px; border-radius: 8px; font-family: monospace; font-size: 11px; word-break: break-all; margin-top: 6px;

            Your report MUST include strictly these 3 cards:
            1. **Top Metric Chips**: Size Change, Impact Rating (e.g. 9/10), New Flags Count, and Native JNI Bridge Count.
            2. **Card 1 - AI Analysis & Executive Summary**: A clean synthesis of what feature updates or architectural changes developers are preparing based on the diffs.
            3. **Card 2 - Unreleased Feature Blueprints**: Specific unreleased feature predictions, accompanied by copyable ADB shell commands in terminal blocks.
            4. **Card 3 - Exact Package Changes**: Clearly listed raw diffs (JNI methods, ProtoBuf schemas, GraphQL queries, endpoints, classes, services, and permissions) with bullet points so technical diffs are obvious.

            RAW CATEGORIZED PACKAGE DIFF DATA:
            {diff_summary}
            """
            
            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
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
