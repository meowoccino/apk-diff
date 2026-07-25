import streamlit as st
import zipfile
import io
import re
import sqlite3
import tempfile
import ctypes
import os
import subprocess
import urllib.request
import shutil
import html
from collections import defaultdict
from PIL import Image
from groq import Groq

# ==================== PAGE SETUP ====================
st.set_page_config(page_title="apk-diff", layout="centered")

# ==================== UTILITY: SANITIZE TEXT ====================
def sanitize(text):
    """Prevents Streamlit from rendering $ as LaTeX math or hiding HTML tags."""
    if not text:
        return ""
    return html.escape(str(text)).replace("$", r"\$")

# ==================== MATERIAL DESIGN 3 — NATIVE MOBILE STYLING ====================
st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        padding-top: 0rem !important;
        margin-top: 0rem !important;
    }

    .main .block-container {
        padding-top: 0.2rem !important;
        padding-bottom: 3rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 480px !important;
    }

    /* Suppress default Streamlit web header/footer elements */
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    [data-testid="manage-app-button"],
    [data-testid="stAppDeployButton"],
    header, footer,
    .viewerBadge_container__1QSob,
    .styles_viewerBadge__1yB5_ {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
        width: 0px !important;
        opacity: 0 !important;
    }

    .stApp {
        background-color: #F8F9FA;
        color: #1D1B20;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Roboto', sans-serif;
    }

    /* ---- Native Header Card ---- */
    .hero-card {
        background: #FFFFFF;
        border: 1px solid #E7E0EC;
        border-radius: 20px;
        padding: 16px;
        margin-top: 4px;
        margin-bottom: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .hero-title-row { display: flex; align-items: center; gap: 12px; }
    .icon-badge {
        background-color: #6750A4;
        color: #fff;
        width: 38px; height: 38px;
        border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
        box-shadow: 0 2px 6px rgba(103,80,164,0.25);
    }
    .hero-title { font-size: 20px; font-weight: 800; color: #1D1B20; letter-spacing: -0.01em; }
    .hero-sub { font-size: 13px; color: #49454F; line-height: 1.4; margin-top: 6px; }
    
    .hero-pillrow { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
    .hero-pill {
        background: #F3EDF7;
        color: #21005D;
        font-size: 11px; font-weight: 600;
        padding: 4px 10px; border-radius: 100px;
    }

    /* ---- Section Labels ---- */
    .section-label {
        font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
        color: #6750A4; text-transform: uppercase;
        margin: 12px 4px 8px 4px; /* Reduced gap */
    }

    /* ---- Native File Upload Cards ---- */
    div[data-testid="stFileUploader"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E7E0EC !important;
        border-radius: 16px !important;
        padding: 12px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.02) !important;
    }
    div[data-testid="stFileUploader"] small { display: none !important; }

    /* ---- Native MD3 Action Button (Smaller Pill) ---- */
    div.stButton > button {
        background: #6750A4 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 100px !important;
        padding: 8px 16px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 6px rgba(103, 80, 164, 0.2) !important;
        margin-top: 6px;
        margin-bottom: 6px;
        min-height: 42px !important;
        width: 100%;
    }
    div.stButton > button:active {
        transform: scale(0.98) !important;
    }

    /* ---- Native Expanders ---- */
    [data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E7E0EC !important;
        border-radius: 16px !important;
        margin-bottom: 10px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.03) !important;
        overflow: hidden !important;
    }
    [data-testid="stExpander"] summary { padding: 14px 16px !important; }
    [data-testid="stExpander"] summary p { font-weight: 600 !important; color: #1D1B20 !important; font-size: 14px !important; }
    [data-testid="stExpander"] summary:hover { background-color: #F8F9FA !important; }

    /* ---- Modern Multi-Wave Radar Animation ---- */
    .scanner-box {
        background: #FFFFFF;
        color: #21005D;
        padding: 24px 16px;
        border-radius: 24px;
        text-align: center;
        margin-top: 10px;
        margin-bottom: 16px;
        border: 1px solid #E7E0EC;
        box-shadow: 0 4px 16px rgba(103,80,164,0.08);
    }
    .pulse-container {
        position: relative;
        width: 48px; height: 48px;
        margin: 0 auto 12px auto;
        display: flex; align-items: center; justify-content: center;
    }
    .radar-ring {
        position: absolute;
        width: 100%; height: 100%;
        border: 3px solid #6750A4;
        border-top-color: transparent;
        border-radius: 50%;
        animation: spin 0.9s infinite linear;
    }
    .radar-core {
        width: 18px; height: 18px;
        background: #6750A4;
        border-radius: 50%;
        animation: pulse-core 1.2s infinite ease-in-out;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    @keyframes pulse-core { 0% { transform: scale(0.8); opacity: 0.7; } 50% { transform: scale(1.15); opacity: 1; } 100% { transform: scale(0.8); opacity: 0.7; } }

    /* ---- Native Fact Cards ---- */
    .tile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
    .tile {
        background: #FFFFFF;
        border: 1px solid #E7E0EC;
        border-radius: 14px;
        padding: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    .tile-val { font-size: 16px; font-weight: 800; color: #21005D; }
    .tile-lbl { font-size: 10px; color: #6F6A76; font-weight: 600; margin-top: 2px; }

    .chip-row { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0 18px 0; }
    .chip {
        background: #F3EDF7; color: #21005D;
        font-size: 11px; font-weight: 600;
        padding: 5px 12px; border-radius: 100px;
    }
    .chip-warn { background: #FFEAEE; color: #410E0B; }
    .chip-ok { background: #E6F4EA; color: #0B3B12; }

    /* ---- Tabs styling ---- */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] {
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 8px 12px !important;
    }

    .mono-block {
        background-color: #F8F9FA; color: #1D1B20;
        border: 1px solid #E7E0EC;
        padding: 10px 12px; border-radius: 8px;
        font-family: 'SFMono-Regular', Consolas, monospace;
        font-size: 11px; word-break: break-all;
        margin-top: 4px; margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ALWAYS RENDER THE HEADER FIRST
st.markdown("""
<div class="hero-card">
    <div class="hero-title-row">
        <div class="icon-badge">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
        </div>
        <div class="hero-title">apk-diff</div>
    </div>
    <div class="hero-sub">Diffs two package builds and surfaces JNI exports, GraphQL/ProtoBuf schemas, DEX class changes, databases, split bundles, third-party SDKs, exposed secrets, architectures, locales, and signing metadata.</div>
    <div class="hero-pillrow">
        <span class="hero-pill">JNI / Native</span>
        <span class="hero-pill">SDK Ecosystem</span>
        <span class="hero-pill">Secrets Scan</span>
        <span class="hero-pill">Locales / ABI</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ==================== JADX DECOMPILER SETUP ====================
def setup_jadx():
    if not os.path.exists("jadx"):
        with st.spinner("Preparing extraction engine..."):
            jadx_zip_path = os.path.join(tempfile.gettempdir(), "jadx.zip")
            urllib.request.urlretrieve("https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip", jadx_zip_path)
            with zipfile.ZipFile(jadx_zip_path, 'r') as zip_ref:
                zip_ref.extractall("jadx")
            os.chmod("jadx/bin/jadx", 0o755)

def decompile_apk(file_bytes, filename):
    try:
        setup_jadx()
        apk_path = os.path.join(tempfile.gettempdir(), filename)
        with open(apk_path, "wb") as f:
            f.write(file_bytes)
            
        out_dir = os.path.join(tempfile.gettempdir(), f"jadx_out_{re.sub(r'[^a-zA-Z0-9]', '_', filename)}")
        os.makedirs(out_dir, exist_ok=True)
        
        with st.spinner(f"Extracting source from {filename}..."):
            subprocess.run(["jadx/bin/jadx", "-d", out_dir, "-r", "--show-bad-code", apk_path], check=False)
            
        zip_base_path = os.path.join(tempfile.gettempdir(), f"{filename}_source")
        archive_path = shutil.make_archive(zip_base_path, 'zip', out_dir)
        
        with open(archive_path, "rb") as f:
            return f.read()
    except Exception as e:
        st.error(f"Extraction encountered an issue: {e}")
        return None

# ==================== SESSION STATE ====================
for key, default in [
    ("report_html", None),
    ("added_image_keys", []),
    ("new_data_images", {}),
    ("quickfacts", None),
    ("jadx_ready", False),
    ("jadx_zip_bytes", None)
]:
    if key not in st.session_state:
        st.session_state[key] = default

NOISE_PATTERNS = [
    "androidx/", "com/google/android/", "kotlin/", "java/", "javax/",
    "android/support/", "org/apache/", "com/facebook/", "io/reactivex/",
    "Ljava/", "Lkotlin/", "Landroid/", "Landroidx/"
]

SDK_SIGNATURES = {
    "Firebase Analytics": ["firebase/analytics"],
    "Firebase Crashlytics": ["crashlytics"],
    "Firebase Cloud Messaging": ["firebase/messaging", "firebase/iid"],
    "Firebase Remote Config": ["firebase/remoteconfig"],
    "Google AdMob": ["google/android/gms/ads", "admob"],
    "Facebook SDK": ["com/facebook/"],
    "Unity Ads": ["unity3d/ads", "unityads"],
    "AppsFlyer": ["appsflyer"],
    "Braze (Appboy)": ["appboy", "braze"],
    "Mixpanel": ["mixpanel"],
    "Amplitude": ["amplitude"],
    "OneSignal": ["onesignal"],
    "Stripe": ["com/stripe/"],
    "Segment": ["com/segment/analytics"],
    "Adjust": ["adjust/sdk"],
    "Sentry": ["io/sentry"],
    "Datadog": ["com/datadog"],
    "Chartboost": ["chartboost"],
    "IronSource": ["ironsource"],
    "Vungle": ["vungle"],
    "InMobi": ["inmobi"],
    "AppLovin": ["applovin"],
    "Bugsnag": ["bugsnag"],
    "WorkManager": ["androidx/work"],
    "ExoPlayer / Media3": ["google/android/exoplayer", "androidx/media3"],
    "gRPC": ["io/grpc"],
    "Retrofit": ["retrofit2"],
    "OkHttp": ["okhttp3"],
    "Room": ["androidx/room"],
    "WebRTC": ["org/webrtc"],
}

SECRET_PATTERNS = {
    "Google API Key": r'AIza[0-9A-Za-z\-_]{35}',
    "AWS Access Key ID": r'AKIA[0-9A-Z]{16}',
    "Stripe Live Secret Key": r'sk_live_[0-9a-zA-Z]{20,}',
    "Stripe Publishable Key": r'pk_live_[0-9a-zA-Z]{20,}',
    "Slack Token": r'xox[baprs]-[0-9A-Za-z\-]{10,}',
    "Firebase Realtime DB URL": r'https://[a-zA-Z0-9\-]+\.firebaseio\.com',
    "JWT-looking Token": r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}',
}

def is_framework_noise(token):
    token_lower = token.lower()
    return any(noise in token_lower for noise in NOISE_PATTERNS)

UI_TEXT_SKIP_SUBSTR = (
    "://", ".png", ".jpg", ".webp", ".xml", ".so", ".dex", ".ttf", ".otf",
    "androidx", "kotlin.", "java.", "com.google", "com.android",
)

def looks_like_ui_text(s):
    if not (2 <= len(s) <= 140): return False
    if "/" in s or "\\" in s: return False
    if any(sub in s for sub in UI_TEXT_SKIP_SUBSTR): return False
    has_space = " " in s
    has_lower = any(c.islower() for c in s)
    has_letter = any(c.isalpha() for c in s)
    if not has_letter: return False
    return has_space or has_lower or "_" in s

def demangle_cpp_symbol(mangled_str):
    try:
        for libname in ['libstdc++.so.6', 'libcxxabi.so.1', 'libc.so.6']:
            try:
                lib = ctypes.CDLL(libname)
                if hasattr(lib, '__cxa_demangle'):
                    cxa = lib.__cxa_demangle
                    cxa.restype = ctypes.c_char_p
                    res = cxa(mangled_str.encode('utf-8'), None, None, None)
                    if res: return res.decode('utf-8', errors='ignore')
            except Exception: continue
    except Exception: pass
    return mangled_str

def inspect_sqlite_db(raw_bytes):
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
                if tbl and not tbl.startswith("sqlite_"): schema_info.add(f"Table: {tbl}")
            conn.close()
    except Exception: pass
    return schema_info

def check_xor_obfuscation(raw_bytes):
    found_urls = set()
    target = b"http"
    for key in range(1, 256):
        xored_target = bytes([b ^ key for b in target])
        if xored_target in raw_bytes:
            pos = raw_bytes.find(xored_target)
            chunk = raw_bytes[pos:pos + 120]
            decoded_chunk = bytes([b ^ key for b in chunk])
            urls = re.findall(r'https?://[A-Za-z0-9_./\-]+', decoded_chunk.decode('ascii', errors='ignore'))
            for u in urls:
                if len(u) < 100: found_urls.add(u)
            if len(found_urls) >= 8: break
    return found_urls

def extract_strings_from_bytes(raw_bytes):
    strings = set()
    matches = re.findall(rb'[\x20-\x7E]{5,}', raw_bytes)
    for m in matches:
        try:
            decoded = m.decode('ascii', errors='ignore').strip()
            if len(decoded) < 120 and decoded and not is_framework_noise(decoded):
                strings.add(decoded)
        except Exception: pass
    return strings

def categorize_file(lower_name):
    if lower_name.endswith(".dex"): return "Dalvik Bytecode (DEX)"
    if lower_name.endswith(".so"): return "Native Libraries (.so)"
    if lower_name.endswith((".png", ".webp", ".jpg", ".jpeg", ".gif")): return "Images"
    if lower_name.endswith(".arsc"): return "Compiled Resources (ARSC)"
    if lower_name.endswith((".db", ".sqlite")): return "Databases"
    if lower_name.endswith((".ttf", ".otf")): return "Fonts"
    if lower_name.endswith(".xml"): return "XML Resources"
    if lower_name.startswith("meta-inf/"): return "Signing / Metadata"
    if lower_name.startswith("assets/"): return "Raw Assets"
    return "Other"

def detect_architectures(files):
    archs = set()
    for f in files:
        m = re.match(r'lib/([^/]+)/', f)
        if m: archs.add(m.group(1))
    return archs

def detect_locales(files):
    locales = set()
    for f in files:
        m = re.search(r'values-([a-zA-Z]{2}(?:-r[A-Z]{2})?)/', f)
        if m: locales.add(m.group(1))
    return locales

def detect_signing_info(files):
    info = set()
    for f in files:
        low = f.lower()
        if low.startswith("meta-inf/") and low.endswith((".rsa", ".dsa", ".ec")):
            info.add(f"Certificate file: {f}")
        if low.endswith("stamp-cert-sha256"):
            info.add("Play Store signing stamp present")
    return info

def detect_split_bundles(files):
    splits = set()
    for f in files:
        m = re.search(r'(config\.[a-zA-Z0-9_]+|split_[a-zA-Z0-9_]+)\.apk', f)
        if m: splits.add(m.group(1))
    return splits

def detect_third_party_sdks(class_paths, config_strings):
    found = set()
    haystacks = [t.lower() for t in class_paths] + [t.lower() for t in list(config_strings)[:3000]]
    for sdk_name, sigs in SDK_SIGNATURES.items():
        for sig in sigs:
            if any(sig.lower() in h for h in haystacks):
                found.add(sdk_name)
                break
    return found

def scan_for_secrets(token_sets):
    findings = set()
    pool = []
    for s in token_sets: pool.extend(list(s)[:4000])
    for pattern_name, pattern in SECRET_PATTERNS.items():
        for tok in pool:
            m = re.search(pattern, tok)
            if m:
                findings.add(f"{pattern_name} → {m.group(0)[:44]}")
                break
        if len(findings) > 25: break
    return findings

def process_zip_archive(zip_obj, details):
    for name in zip_obj.namelist():
        info = zip_obj.getinfo(name)

        if name.endswith('.apk') and name != zip_obj.filename:
            try:
                sub_apk_bytes = zip_obj.read(name)
                with zipfile.ZipFile(io.BytesIO(sub_apk_bytes), "r") as sub_z:
                    process_zip_archive(sub_z, details)
            except Exception: pass
            continue

        details["files"].add(name)
        details["total_size"] += info.file_size
        lower_name = name.lower()
        category = categorize_file(lower_name)
        details["category_sizes"][category] = details["category_sizes"].get(category, 0) + info.file_size

        if name.endswith('/') or info.file_size == 0: continue

        if any(lower_name.endswith(ext) for ext in ['.png', '.webp', '.jpg']) and info.file_size < 300 * 1024:
            if not any(ignore in lower_name for ignore in ["icon", "launcher", "splash"]):
                try: details["images"][name.split('/')[-1]] = zip_obj.read(name)
                except Exception: pass

        try:
            raw_bytes = zip_obj.read(name) if info.file_size < 10 * 1024 * 1024 else zip_obj.open(name).read(5 * 1024 * 1024)

            if any(lower_name.endswith(ext) for ext in [".db", ".sqlite"]):
                details["db_schemas"].update(inspect_sqlite_db(raw_bytes))

            proto_matches = re.findall(rb'type\.googleapis\.com/[A-Za-z0-9_.-]+', raw_bytes)
            for pm in proto_matches: details["protobuf_schemas"].add(pm.decode('ascii', errors='ignore'))

            graphql_matches = re.findall(rb'(?:query|mutation)\s+[A-Za-z0-9_]+', raw_bytes)
            for gqm in graphql_matches: details["graphql_ops"].add(gqm.decode('ascii', errors='ignore'))

            jni_matches = re.findall(rb'Java_[A-Za-z0-9_]+', raw_bytes)
            for jm in jni_matches: details["jni_exports"].add(jm.decode('ascii', errors='ignore'))

            if lower_name.endswith(".dex"):
                class_matches = re.findall(rb'L[a-zA-Z0-9_$]+/[a-zA-Z0-9_$]+;', raw_bytes)
                for cm in class_matches[:150]:
                    decoded_cls = cm.decode('ascii', errors='ignore')
                    if not is_framework_noise(decoded_cls): details["class_paths"].add(decoded_cls)

                anno_matches = re.findall(rb'(?:SerializedName|Keep|Beta|Experimental|RequiresOptIn)[A-Za-z0-9_"\':\s]{2,60}', raw_bytes)
                for am in anno_matches:
                    try: details["annotations"].add(am.decode('ascii', errors='ignore').strip())
                    except Exception: pass

            details["xor_urls"].update(check_xor_obfuscation(raw_bytes))
            file_tokens = extract_strings_from_bytes(raw_bytes)

            if lower_name.endswith(".so"):
                for token in file_tokens:
                    if token.startswith("_Z"): details["native_strings"].add(demangle_cpp_symbol(token))
                    else: details["native_strings"].add(token)
            elif any(lower_name.endswith(ext) for ext in [".csv", ".json", ".proto", ".txt", ".dat", ".xml", ".properties"]):
                details["config_strings"].update(file_tokens)
            else:
                details["all_strings"].update(file_tokens)

            if lower_name.endswith("resources.arsc") or lower_name.endswith(".arsc"):
                details["ui_strings"].update(t for t in file_tokens if looks_like_ui_text(t))

            for token in file_tokens:
                token_lower = token.lower()
                if "permission." in token_lower: details["permissions"].add(token)
                elif "activity" in token_lower or "screen" in token_lower: details["activities"].add(token)
                elif "service" in token_lower or "receiver" in token_lower: details["services"].add(token)
                elif token_lower.startswith("http://") or token_lower.startswith("https://"): details["endpoints"].add(token)
                elif "scheme://" in token_lower or "://" in token_lower: details["deep_links"].add(token)
        except Exception: pass

def inspect_entire_bundle(file_bytes):
    details = {
        "files": set(), "total_size": 0, "all_strings": set(), "native_strings": set(), "config_strings": set(),
        "annotations": set(), "protobuf_schemas": set(), "graphql_ops": set(), "jni_exports": set(), "class_paths": set(),
        "db_schemas": set(), "xor_urls": set(), "activities": set(), "services": set(), "permissions": set(),
        "deep_links": set(), "endpoints": set(), "images": {}, "category_sizes": {}, "ui_strings": set(),
    }
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            process_zip_archive(z, details)
    except Exception as e:
        st.error(f"Error reading package bundle: {e}")

    details["architectures"] = detect_architectures(details["files"])
    details["locales"] = detect_locales(details["files"])
    details["signing_info"] = detect_signing_info(details["files"])
    details["splits"] = detect_split_bundles(details["files"])
    details["third_party_sdks"] = detect_third_party_sdks(details["class_paths"], details["config_strings"])
    return details

def render_quickfacts(old_data, new_data):
    old_size_mb = round(old_data["total_size"] / (1024 * 1024), 2)
    new_size_mb = round(new_data["total_size"] / (1024 * 1024), 2)
    size_diff = round(new_size_mb - old_size_mb, 2)

    new_archs = new_data["architectures"] - old_data["architectures"]
    new_locales = new_data["locales"] - old_data["locales"]
    new_sdks = new_data["third_party_sdks"] - old_data["third_party_sdks"]
    removed_sdks = old_data["third_party_sdks"] - new_data["third_party_sdks"]
    new_splits = new_data["splits"] - old_data["splits"]
    secrets_new = scan_for_secrets([
        new_data["all_strings"] - old_data["all_strings"],
        new_data["config_strings"] - old_data["config_strings"],
        new_data["native_strings"] - old_data["native_strings"],
    ])

    st.markdown('<div class="section-label">QUICK FACTS (NO AI)</div>', unsafe_allow_html=True)

    tiles = f"""
    <div class="tile-grid">
        <div class="tile"><div class="tile-val">{'+' if size_diff >= 0 else ''}{size_diff} MB</div><div class="tile-lbl">SIZE CHANGE ({old_size_mb}→{new_size_mb} MB)</div></div>
        <div class="tile"><div class="tile-val">{len(new_data['files']) - len(old_data['files']):+d}</div><div class="tile-lbl">FILE COUNT CHANGE</div></div>
        <div class="tile"><div class="tile-val">{len(new_sdks)}</div><div class="tile-lbl">NEW 3RD-PARTY SDKS</div></div>
        <div class="tile"><div class="tile-val">{len(new_data['jni_exports'] - old_data['jni_exports'])}</div><div class="tile-lbl">NEW JNI EXPORTS</div></div>
    </div>
    """
    st.markdown(tiles, unsafe_allow_html=True)

    chips = '<div class="chip-row">'
    for a in sorted(new_archs): chips += f'<span class="chip">New arch: {sanitize(a)}</span>'
    for l in sorted(new_locales)[:8]: chips += f'<span class="chip">New locale: {sanitize(l)}</span>'
    for s in sorted(new_splits): chips += f'<span class="chip">Split: {sanitize(s)}</span>'
    if not new_archs and not new_locales and not new_splits:
        chips += '<span class="chip">No new architectures / locales / splits</span>'
    chips += '</div>'
    st.markdown(chips, unsafe_allow_html=True)

    if secrets_new:
        st.markdown('<div class="chip-row"><span class="chip chip-warn">Possible exposed secrets found</span></div>', unsafe_allow_html=True)
        with st.expander(f"Potential exposed secrets ({len(secrets_new)})"):
            for s in sorted(secrets_new):
                st.markdown(f'<div class="mono-block">{sanitize(s)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="chip-row" style="margin-bottom: 20px;"><span class="chip chip-ok">No hardcoded secrets matched</span></div>', unsafe_allow_html=True)

    with st.expander("Third-party SDK ecosystem"):
        if new_sdks:
            st.markdown("**Newly added:**")
            st.markdown('<div class="chip-row">' + "".join(f'<span class="chip chip-ok">{sanitize(s)}</span>' for s in sorted(new_sdks)) + '</div>', unsafe_allow_html=True)
        if removed_sdks:
            st.markdown("**Removed:**")
            st.markdown('<div class="chip-row">' + "".join(f'<span class="chip chip-warn">{sanitize(s)}</span>' for s in sorted(removed_sdks)) + '</div>', unsafe_allow_html=True)
        st.markdown("**All SDKs detected in new build:**")
        st.markdown('<div class="chip-row">' + "".join(f'<span class="chip">{sanitize(s)}</span>' for s in sorted(new_data["third_party_sdks"])) + '</div>', unsafe_allow_html=True)

    with st.expander("Size breakdown by category (new build)"):
        cats = sorted(new_data["category_sizes"].items(), key=lambda x: -x[1])
        for cat, size in cats:
            mb = round(size / (1024 * 1024), 2)
            if mb > 0.01: st.markdown(f"**{sanitize(cat)}** — {mb} MB")

    with st.expander("Signing & packaging metadata"):
        sign_new = new_data["signing_info"]
        if sign_new:
            for s in sorted(sign_new): st.markdown(f"- {sanitize(s)}")
        else:
            st.markdown("_No META-INF signature files found in this archive._")
        if new_data["architectures"]:
            st.markdown(f"**Architectures shipped:** {', '.join(sorted(new_data['architectures']))}")
        if new_data["locales"]:
            st.markdown(f"**Locales included:** {len(new_data['locales'])} ({', '.join(sorted(new_data['locales'])[:15])}{'…' if len(new_data['locales']) > 15 else ''})")

    added_ui = sorted(new_data["ui_strings"] - old_data["ui_strings"])
    removed_ui = sorted(old_data["ui_strings"] - new_data["ui_strings"])
    
    added_ui_clean = [s for s in added_ui if s.strip()]
    removed_ui_clean = [s for s in removed_ui if s.strip()]

    with st.expander(f"New UI-facing text / labels ({len(added_ui_clean)})"):
        if added_ui_clean or removed_ui_clean:
            full_ui_export = f"=== ADDED UI TEXTS ({len(added_ui_clean)}) ===\n" + "\n".join(added_ui_clean) + f"\n\n=== REMOVED UI TEXTS ({len(removed_ui_clean)}) ===\n" + "\n".join(removed_ui_clean)
            st.download_button(
                label=f"Download Full UI Text Diff ({len(added_ui_clean)} new)",
                data=full_ui_export,
                file_name="apk_diff_ui_texts.txt",
                mime="text/plain",
                use_container_width=True
            )

            ui_search_query = st.text_input("Search UI Texts:", placeholder="Filter UI texts...", key="ui_search")

            if ui_search_query.strip():
                sq_ui = ui_search_query.strip().lower()
                filtered_ui_added = [s for s in added_ui_clean if sq_ui in s.lower()]
                filtered_ui_removed = [s for s in removed_ui_clean if sq_ui in s.lower()]
                st.caption(f"Showing matches for '{sanitize(ui_search_query)}': {len(filtered_ui_added)} added, {len(filtered_ui_removed)} removed")
                
                tab_ui_add, tab_ui_rem = st.tabs([f"Added ({len(filtered_ui_added)})", f"Removed ({len(filtered_ui_removed)})"])
                with tab_ui_add:
                    for s in filtered_ui_added[:300]: st.markdown(f"- {sanitize(s)}")
                with tab_ui_rem:
                    for s in filtered_ui_removed[:300]: st.markdown(f"- ~~{sanitize(s)}~~")
            else:
                if added_ui_clean:
                    for s in added_ui_clean[:250]: st.markdown(f"- {sanitize(s)}")
                    if len(added_ui_clean) > 250: st.caption(f"…and {len(added_ui_clean) - 250} more. Download the text file above for all items.")
                
                if removed_ui_clean:
                    st.markdown(f"**Removed ({len(removed_ui_clean)}):**")
                    for s in removed_ui_clean[:100]: st.markdown(f"- ~~{sanitize(s)}~~")
                    if len(removed_ui_clean) > 100: st.caption(f"…and {len(removed_ui_clean) - 100} more. Download the text file above for all items.")
        else:
            st.markdown("_No new UI copy detected between builds._")

    with st.expander("Raw string diff — unfiltered (no AI)"):
        raw_added = sorted((new_data["all_strings"] | new_data["config_strings"]) - (old_data["all_strings"] | old_data["config_strings"]))
        raw_removed = sorted((old_data["all_strings"] | old_data["config_strings"]) - (new_data["all_strings"] | new_data["config_strings"]))
        
        raw_added_clean = [s for s in raw_added if s.strip()]
        raw_removed_clean = [s for s in raw_removed if s.strip()]

        full_text_export = f"=== ADDED STRINGS ({len(raw_added_clean)}) ===\n" + "\n".join(raw_added_clean) + f"\n\n=== REMOVED STRINGS ({len(raw_removed_clean)}) ===\n" + "\n".join(raw_removed_clean)
        st.download_button(
            label=f"Download Full Raw String Diff ({len(raw_added_clean) + len(raw_removed_clean)} items)",
            data=full_text_export,
            file_name="apk_diff_raw_strings.txt",
            mime="text/plain",
            use_container_width=True
        )

        search_query = st.text_input("Search Raw Strings:", placeholder="Filter strings...", key="str_search")

        if search_query.strip():
            sq = search_query.strip().lower()
            filtered_added = [s for s in raw_added_clean if sq in s.lower()]
            filtered_removed = [s for s in raw_removed_clean if sq in s.lower()]
            st.caption(f"Showing matches for '{sanitize(search_query)}': {len(filtered_added)} added, {len(filtered_removed)} removed")
            
            tab_add, tab_rem = st.tabs([f"Added ({len(filtered_added)})", f"Removed ({len(filtered_removed)})"])
            with tab_add:
                for s in filtered_added[:300]: st.markdown(f'<div class="mono-block">{sanitize(s)}</div>', unsafe_allow_html=True)
            with tab_rem:
                for s in filtered_removed[:300]: st.markdown(f'<div class="mono-block">{sanitize(s)}</div>', unsafe_allow_html=True)
        else:
            tab_add, tab_rem = st.tabs([f"Added ({len(raw_added_clean)})", f"Removed ({len(raw_removed_clean)})"])
            with tab_add:
                for s in raw_added_clean[:250]: st.markdown(f'<div class="mono-block">{sanitize(s)}</div>', unsafe_allow_html=True)
                if len(raw_added_clean) > 250: st.caption(f"…and {len(raw_added_clean) - 250} more. Download the text file above for all items.")
            with tab_rem:
                for s in raw_removed_clean[:250]: st.markdown(f'<div class="mono-block">{sanitize(s)}</div>', unsafe_allow_html=True)
                if len(raw_removed_clean) > 250: st.caption(f"…and {len(raw_removed_clean) - 250} more. Download the text file above for all items.")

# ==================== FULLSCREEN REPORT VIEW ====================
if st.session_state.report_html:
    if st.session_state.added_image_keys:
        with st.expander("Newly Added Graphic Previews", expanded=False):
            img_cols = st.columns(min(len(st.session_state.added_image_keys[:4]), 4))
            for idx, img_key in enumerate(st.session_state.added_image_keys[:4]):
                with img_cols[idx]:
                    try:
                        image = Image.open(io.BytesIO(st.session_state.new_data_images[img_key]))
                        st.image(image, caption=img_key[:15], width=70)
                    except Exception:
                        pass

    if st.session_state.quickfacts:
        old_q, new_q = st.session_state.quickfacts
        render_quickfacts(old_q, new_q)

    st.markdown('<div class="section-label">AI TEARDOWN REPORT</div>', unsafe_allow_html=True)
    st.markdown(st.session_state.report_html, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True) # Fills the gap cleanly
    if st.button("Extract Java Source Code", use_container_width=True):
        zip_bytes = decompile_apk(st.session_state.new_file_bytes, st.session_state.new_file_name)
        if zip_bytes:
            st.session_state.jadx_zip_bytes = zip_bytes
            st.session_state.jadx_ready = True
            st.rerun()
        
    if st.session_state.jadx_ready and st.session_state.jadx_zip_bytes:
        st.download_button(
            label="Download Source Archive (.zip)",
            data=st.session_state.jadx_zip_bytes,
            file_name=f"{st.session_state.new_file_name}_java_source.zip",
            mime="application/zip",
            use_container_width=True
        )

    st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
    if st.button("Start New Scan", use_container_width=True):
        st.session_state.report_html = None
        st.session_state.added_image_keys = []
        st.session_state.new_data_images = {}
        st.session_state.quickfacts = None
        st.session_state.jadx_ready = False
        st.session_state.jadx_zip_bytes = None
        st.rerun()

# ==================== MAIN INPUT VIEW ====================
else:
    old_file = st.file_uploader("Old Version (.apk, .aab, .xapk, .apks)", type=["apk", "aab", "xapk", "apks", "zip"])
    new_file = st.file_uploader("New Version (.apk, .aab, .xapk, .apks)", type=["apk", "aab", "xapk", "apks", "zip"])

    if st.button("Run Deep Package Teardown", use_container_width=True):
        if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
            st.error("GROQ_API_KEY is missing from Streamlit Secrets!")
        elif not old_file or not new_file:
            st.error("Please upload both Old and New package files.")
        else:
            st.session_state.new_file_bytes = new_file.read()
            st.session_state.new_file_name = new_file.name
            
            old_file.seek(0)
            new_file.seek(0)
            
            scanner_placeholder = st.empty()

            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="pulse-container">
                    <div class="radar-ring"></div>
                    <div class="radar-core"></div>
                </div>
                <div style="font-weight: 800; font-size: 16px; color: #21005D;">Decompressing Archives & Native JNI Bridges</div>
                <div style="font-size: 13px; color: #49454F; margin-top: 4px;">Demangling C++ symbols, mapping GraphQL & ProtoBufs...</div>
            </div>
            """, unsafe_allow_html=True)

            old_bytes = old_file.read()
            new_bytes = st.session_state.new_file_bytes

            old_data = inspect_entire_bundle(old_bytes)
            new_data = inspect_entire_bundle(new_bytes)
            st.session_state.quickfacts = (old_data, new_data)

            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="pulse-container">
                    <div class="radar-ring"></div>
                    <div class="radar-core"></div>
                </div>
                <div style="font-weight: 800; font-size: 16px; color: #21005D;">Diffing Bytecode, SDKs & Metadata</div>
                <div style="font-size: 13px; color: #49454F; margin-top: 4px;">Scanning for exposed secrets, ABI splits, locale diffs...</div>
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

            added_ui_strings = list(new_data["ui_strings"] - old_data["ui_strings"])
            added_sdks = list(new_data["third_party_sdks"] - old_data["third_party_sdks"])
            removed_sdks = list(old_data["third_party_sdks"] - new_data["third_party_sdks"])
            added_archs = list(new_data["architectures"] - old_data["architectures"])
            added_locales = list(new_data["locales"] - old_data["locales"])
            secrets_found = list(scan_for_secrets([
                new_data["all_strings"] - old_data["all_strings"],
                new_data["config_strings"] - old_data["config_strings"],
                new_data["native_strings"] - old_data["native_strings"],
            ]))

            st.session_state.added_image_keys = [k for k in new_data["images"].keys() if k not in old_data["images"]]
            st.session_state.new_data_images = new_data["images"]

            old_size_mb = round(old_data["total_size"] / (1024 * 1024), 2)
            new_size_mb = round(new_data["total_size"] / (1024 * 1024), 2)
            size_diff_mb = round(new_size_mb - old_size_mb, 2)

            # INCREASED AI DATA LIMITS (Providing 3-4x more context safely)
            combined_diffs = added_native[:60] + added_configs[:60] + added_general[:60] + added_annotations[:40] + added_jni[:40]
            feature_toggles = list(set([t for t in combined_diffs if any(k in t.lower() for k in ['flag', 'enable', 'config', 'opt', 'toggle', 'experiment', 'beta'])]))

            diff_summary = f"""
            === PACKAGE META ===
            SIZE CHANGE: {size_diff_mb} MB
            
            === 1. FEATURE TOGGLES & ANNOTATIONS ===
            FLAGS: {feature_toggles[:40]}
            ANNOTATIONS: {added_annotations[:30]}

            === 2. JNI NATIVE C++ BRIDGES & SYMBOLS ===
            JNI EXPORTS: {added_jni[:30]}
            DEMANGLED C++ SYMBOLS: {added_native[:30]}

            === 3. GRAPHQL, PROTOBUFS & DATABASES ===
            GRAPHQL QUERIES: {added_graphql[:30]}
            PROTOBUFS: {added_protobufs[:30]}
            DB TABLES: {added_dbs[:30]}

            === 4. BYTECODE CLASS HIERARCHY DIFFS ===
            CLASSES: {added_classes[:40]}

            === 5. SERVER ENDPOINTS & DEEP LINKS ===
            ENDPOINTS: {added_endpoints[:30]}
            SCHEMES: {added_deep_links[:30]}

            === 6. NEW SCREENS & BACKGROUND SERVICES ===
            ACTIVITIES: {added_activities[:30]}
            SERVICES: {added_services[:30]}
            PERMISSIONS: {added_permissions[:30]}

            === 7. THIRD-PARTY SDK ECOSYSTEM ===
            NEW SDKs: {added_sdks}
            REMOVED SDKs: {removed_sdks}

            === 8. POTENTIAL EXPOSED SECRETS ===
            {secrets_found[:30]}

            === 9. NEW UI-FACING TEXT / LABELS ===
            {added_ui_strings[:40]}
            """

            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="pulse-container">
                    <div class="radar-ring"></div>
                    <div class="radar-core"></div>
                </div>
                <div style="font-weight: 800; font-size: 16px; color: #21005D;">Synthesizing AI Teardown Report</div>
                <div style="font-size: 13px; color: #49454F; margin-top: 4px;">Formulating unreleased predictions & technical audits...</div>
            </div>
            """, unsafe_allow_html=True)

            client = Groq(api_key=st.secrets["GROQ_API_KEY"])

            prompt = f"""
            You are a lead mobile software investigator analyzing an APK diff. Output a clean Material Design 3 HTML dashboard. 
            Do NOT use generic filler text like "The updated package introduces new features and improvements." If a list is empty, state explicitly: "No changes detected." Always explicitly cite the exact class/file names from the provided data.
            Group similar items together (e.g., 'BetaTab' and 'Beta tab' are the same feature). Do not repeat yourself.
            Output strictly raw HTML (no markdown codeblocks). 

            Use the EXACT HTML blocks provided below for the card containers and headers. Do not change the SVG paths or container styles.

            - **Metric Chips Row**: `display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px;`. Pills: `background: #EADDFF; color: #21005D; padding: 4px 10px; border-radius: 100px; font-size: 11px; font-weight: bold;`. Include: Size Change ({size_diff_mb} MB), Impact Rating (e.g. 8/10), New Flags ({len(feature_toggles)}), New JNI Bridges ({len(added_jni)}), New SDKs ({len(added_sdks)}).

            - **Card 1 (AI Analysis & Executive Summary)**:
              <div style="background-color: #F3EDF7; border-radius: 16px; padding: 14px; margin-bottom: 12px; border-left: 4px solid #6750A4;">
              <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6750A4" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg><span style="font-weight:800;font-size:16px;color:#1D1B20;">AI Analysis & Executive Summary</span></div>
              Write 3-4 specific narrative sentences explaining the actual technical changes.
              </div>

            - **Card 2 (Unreleased Feature Blueprints)**:
              <div style="background-color: #FFD8E4; color: #31111D; border-radius: 16px; padding: 14px; margin-bottom: 12px; border-left: 4px solid #B12B58;">
              <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#B12B58" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg><span style="font-weight:800;font-size:16px;color:#31111D;">Unreleased Feature Blueprints</span></div>
              Provide concrete feature predictions based strictly on the data. Include terminal code blocks (`background-color:#1D1B20;color:#E6E1E5;padding:8px 12px;border-radius:8px;font-family:monospace;font-size:11px;word-break:break-all;margin-top:6px;`) showing example grep/adb commands.
              </div>

            - **Card 3 (Exact Package Technical Diffs)**:
              <div style="background-color: #F7F2FA; border-radius: 16px; padding: 14px; margin-bottom: 12px; border: 1px solid #CAC4D0; border-left: 4px solid #79747E;">
              <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#49454F" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg><span style="font-weight:800;font-size:16px;color:#1D1B20;">Exact Package Technical Diffs</span></div>
              List JNI methods, ProtoBuf schemas, GraphQL, endpoints, and permissions.
              </div>

            - **Card 4 (Security, SDKs & Packaging Risk)**:
              <div style="background-color: #FFF3E0; color: #3E2723; border-radius: 16px; padding: 14px; margin-bottom: 12px; border-left: 4px solid #E8A33D;">
              <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3E2723" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg><span style="font-weight:800;font-size:16px;color:#3E2723;">Security, SDKs & Packaging Risk</span></div>
              Analyze added/removed SDKs and secrets.
              </div>

            RAW DATA:
            {diff_summary}
            """

            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=4000,
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
