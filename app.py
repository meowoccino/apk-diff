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
import json
import time
from PIL import Image
from groq import Groq

# ==================== PAGE SETUP ====================
st.set_page_config(page_title="apk-diff", layout="centered")

# ==================== UTILITY FUNCTIONS ====================
def sanitize(text):
    if not text:
        return ""
    return html.escape(str(text)).replace("$", r"\$")

def clean_json_response(raw_str):
    cleaned = re.sub(r"^```json\s*", "", raw_str, flags=re.MULTILINE)
    cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()

def format_title_case(token):
    if not token:
        return ""
    words = str(token).replace("_", " ").split()
    return " ".join(w.capitalize() for w in words)

# ==================== JADX DECOMPILER SETUP ====================
def setup_jadx():
    if not os.path.exists("jadx"):
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
        
        subprocess.run(["jadx/bin/jadx", "-d", out_dir, "-r", "--show-bad-code", apk_path], check=False)
            
        zip_base_path = os.path.join(tempfile.gettempdir(), f"{filename}_source")
        archive_path = shutil.make_archive(zip_base_path, 'zip', out_dir)
        
        with open(archive_path, "rb") as f:
            return f.read()
    except Exception as e:
        st.error(f"Extraction error: {e}")
        return None

# ==================== STYLING & RADAR ANIMATION ====================
st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        padding-top: 0rem !important; margin-top: 0rem !important;
    }
    .main .block-container {
        padding-top: 0.2rem !important; padding-bottom: 3rem !important;
        padding-left: 0.8rem !important; padding-right: 0.8rem !important;
        max-width: 480px !important;
    }
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stStatusWidget"], [data-testid="manage-app-button"], [data-testid="stAppDeployButton"], header, footer {
        display: none !important; visibility: hidden !important; height: 0px !important;
    }
    .stApp { background-color: #F8F9FA; color: #1D1B20; font-family: -apple-system, sans-serif; }
    
    .hero-card {
        background: #FFFFFF; border: 1px solid #E7E0EC; border-radius: 20px;
        padding: 16px; margin-top: 4px; margin-bottom: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .hero-title { font-size: 20px; font-weight: 800; color: #1D1B20; }
    .hero-sub { font-size: 13px; color: #49454F; line-height: 1.4; margin-top: 6px; }
    .hero-pillrow { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
    .hero-pill { background: #F3EDF7; color: #21005D; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 100px; }
    
    .section-label { font-size: 11px; font-weight: 700; letter-spacing: 0.05em; color: #6750A4; text-transform: uppercase; margin: 12px 4px 8px 4px; }
    div[data-testid="stFileUploader"] { background-color: #FFFFFF !important; border: 1px solid #E7E0EC !important; border-radius: 16px !important; padding: 12px !important; }
    div[data-testid="stFileUploader"] small { display: none !important; }
    div.stButton > button { background: #6750A4 !important; color: #FFFFFF !important; border: none !important; border-radius: 100px !important; padding: 8px 16px !important; font-size: 14px !important; font-weight: 600 !important; width: 100%; min-height: 42px !important; }
    .secondary-btn button { background: #31111D !important; color: #FFD8E4 !important; }

    /* RADAR SCANNER ANIMATION */
    .scanner-box {
        background: #FFFFFF; color: #21005D; padding: 24px 16px; border-radius: 24px;
        text-align: center; margin-top: 10px; margin-bottom: 16px; border: 1px solid #E7E0EC;
        box-shadow: 0 4px 16px rgba(103,80,164,0.08);
    }
    .pulse-container {
        position: relative; width: 48px; height: 48px; margin: 0 auto 12px auto;
        display: flex; align-items: center; justify-content: center;
    }
    .radar-ring {
        position: absolute; width: 100%; height: 100%; border: 3px solid #6750A4;
        border-top-color: transparent; border-radius: 50%; animation: spin 0.9s infinite linear;
    }
    .radar-core {
        width: 18px; height: 18px; background: #6750A4; border-radius: 50%;
        animation: pulse-core 1.2s infinite ease-in-out;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    @keyframes pulse-core { 0% { transform: scale(0.8); opacity: 0.7; } 50% { transform: scale(1.15); opacity: 1; } 100% { transform: scale(0.8); opacity: 0.7; } }

    .tile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
    .tile { background: #FFFFFF; border: 1px solid #E7E0EC; border-radius: 14px; padding: 12px; }
    .tile-val { font-size: 16px; font-weight: 800; color: #21005D; }
    .tile-lbl { font-size: 10px; color: #6F6A76; font-weight: 600; margin-top: 2px; }
    .chip-row { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0 14px 0; }
    .chip { background: #F3EDF7; color: #21005D; font-size: 11px; font-weight: 600; padding: 5px 12px; border-radius: 100px; }
    .chip-warn { background: #FFEAEE; color: #410E0B; }
    .chip-ok { background: #E6F4EA; color: #0B3B12; }
    
    .report-card { border-radius: 16px; padding: 16px; margin-bottom: 12px; }
    .report-card-title { font-weight: 800; font-size: 15px; margin-bottom: 10px; }
    .report-card-body { font-size: 13.5px; line-height: 1.5; }
    .cmd-box { background-color: #1D1B20; color: #E6E1E5; padding: 8px 12px; border-radius: 8px; font-family: monospace; font-size: 11px; word-break: break-all; margin: 8px 0; }
    
    .hunter-card { background: #1D1B20; color: #E6E1E5; border-left: 4px solid #D0BCFF; border-radius: 16px; padding: 16px; margin-bottom: 12px; }
    .hunter-title { font-weight: 800; font-size: 16px; color: #D0BCFF; margin-bottom: 12px; }
    .hunter-evidence { background: #332D41; padding: 10px; border-radius: 8px; font-size: 12.5px; margin-bottom: 10px; }
    .hunter-cmd { background: #000000; color: #00FF00; padding: 10px; border-radius: 8px; font-family: monospace; font-size: 11px; word-break: break-all; }
    .mono-block { background-color: #F8F9FA; color: #1D1B20; border: 1px solid #E7E0EC; padding: 10px 12px; border-radius: 8px; font-family: monospace; font-size: 11px; word-break: break-all; margin: 4px 0; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero-card">
    <div class="hero-title">apk-diff</div>
    <div class="hero-sub">Diffs two package builds and surfaces JNI exports, GraphQL/ProtoBuf schemas, DEX class changes, databases, split bundles, third-party SDKs, exposed secrets, architectures, locales, and signing metadata.</div>
    <div class="hero-pillrow">
        <span class="hero-pill">JNI / Native</span><span class="hero-pill">SDK Ecosystem</span><span class="hero-pill">Secrets Scan</span><span class="hero-pill">Locales / ABI</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Initialize Session States
for key, default in [
    ("report_data", None), ("hunter_data", None), ("scan_mode", None),
    ("added_image_keys", []), ("new_data_images", {}), ("quickfacts", None),
    ("jadx_ready", False), ("jadx_zip_bytes", None), ("new_file_bytes", None), ("new_file_name", "")
]:
    if key not in st.session_state:
        st.session_state[key] = default

NOISE_PATTERNS = ["androidx/", "com/google/android/", "kotlin/", "java/", "javax/", "android/support/", "org/apache/", "com/facebook/", "io/reactivex/", "Ljava/", "Lkotlin/", "Landroid/", "Landroidx/"]
SDK_SIGNATURES = {
    "Firebase Analytics": ["firebase/analytics"], "Firebase Crashlytics": ["crashlytics"], "Firebase Cloud Messaging": ["firebase/messaging", "firebase/iid"], "Firebase Remote Config": ["firebase/remoteconfig"], "Google AdMob": ["google/android/gms/ads", "admob"], "Facebook SDK": ["com/facebook/"], "Unity Ads": ["unity3d/ads", "unityads"], "AppsFlyer": ["appsflyer"], "Braze (Appboy)": ["appboy", "braze"], "Mixpanel": ["mixpanel"], "Amplitude": ["amplitude"], "OneSignal": ["onesignal"], "Stripe": ["com/stripe/"], "Segment": ["com/segment/analytics"], "Adjust": ["adjust/sdk"], "Sentry": ["io/sentry"], "Datadog": ["com/datadog"], "Chartboost": ["chartboost"], "IronSource": ["ironsource"], "Vungle": ["vungle"], "InMobi": ["inmobi"], "AppLovin": ["applovin"], "Bugsnag": ["bugsnag"], "WorkManager": ["androidx/work"], "ExoPlayer / Media3": ["google/android/exoplayer", "androidx/media3"], "gRPC": ["io/grpc"], "Retrofit": ["retrofit2"], "OkHttp": ["okhttp3"], "Room": ["androidx/room"], "WebRTC": ["org/webrtc"],
}
SECRET_PATTERNS = {
    "Google API Key": r'AIza[0-9A-Za-z\-_]{35}', "AWS Access Key ID": r'AKIA[0-9A-Z]{16}', "Stripe Live Secret Key": r'sk_live_[0-9a-zA-Z]{20,}', "Stripe Publishable Key": r'pk_live_[0-9a-zA-Z]{20,}', "Slack Token": r'xox[baprs]-[0-9A-Za-z\-]{10,}', "Firebase Realtime DB URL": r'https://[a-zA-Z0-9\-]+\.firebaseio\.com', "JWT-looking Token": r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}',
}

def is_framework_noise(token):
    return any(noise in token.lower() for noise in NOISE_PATTERNS)

def looks_like_ui_text(s):
    if not (2 <= len(s) <= 140) or "/" in s or "\\" in s: return False
    if any(sub in s for sub in ("://", ".png", ".jpg", ".webp", ".xml", ".so", ".dex", ".ttf", ".otf", "androidx", "kotlin.", "java.", "com.google", "com.android")): return False
    return any(c.isalpha() for c in s) and (" " in s or any(c.islower() for c in s) or "_" in s)

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
            except: continue
    except: pass
    return mangled_str

def inspect_sqlite_db(raw_bytes):
    schema_info = set()
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as tmp:
            tmp.write(raw_bytes); tmp.flush()
            conn = sqlite3.connect(tmp.name); cursor = conn.cursor()
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
            for tbl, sql in cursor.fetchall()[:15]:
                if tbl and not tbl.startswith("sqlite_"): schema_info.add(f"Table: {tbl}")
            conn.close()
    except: pass
    return schema_info

def check_xor_obfuscation(raw_bytes):
    found_urls = set()
    for key in range(1, 256):
        xored_target = bytes([b ^ key for b in b"http"])
        if xored_target in raw_bytes:
            pos = raw_bytes.find(xored_target)
            decoded = bytes([b ^ key for b in raw_bytes[pos:pos + 120]]).decode('ascii', errors='ignore')
            for u in re.findall(r'https?://[A-Za-z0-9_./\-]+', decoded):
                if len(u) < 100: found_urls.add(u)
            if len(found_urls) >= 8: break
    return found_urls

def extract_strings_from_bytes(raw_bytes):
    strings = set()
    for m in re.findall(rb'[\x20-\x7E]{5,}', raw_bytes):
        try:
            dec = m.decode('ascii', errors='ignore').strip()
            if len(dec) < 120 and dec and not is_framework_noise(dec): strings.add(dec)
        except: pass
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
    return "Other"

def scan_for_secrets(string_sets):
    found = set()
    for s_set in string_sets:
        for item in list(s_set)[:2000]:
            for sec_name, pattern in SECRET_PATTERNS.items():
                if re.search(pattern, str(item)):
                    found.add(f"{sec_name}: {item}")
    return found

def process_zip_archive(zip_obj, details):
    for name in zip_obj.namelist():
        info = zip_obj.getinfo(name)
        if name.endswith('.apk') and name != zip_obj.filename:
            try:
                with zipfile.ZipFile(io.BytesIO(zip_obj.read(name)), "r") as sub_z: process_zip_archive(sub_z, details)
            except: pass
            continue
        details["files"].add(name)
        details["total_size"] += info.file_size
        lower_name = name.lower()
        category = categorize_file(lower_name)
        details["category_sizes"][category] = details["category_sizes"].get(category, 0) + info.file_size
        if name.endswith('/') or info.file_size == 0: continue

        if any(lower_name.endswith(ext) for ext in ['.png', '.webp', '.jpg']) and info.file_size < 300 * 1024:
            if not any(ignore in lower_name for ignore in ["icon", "launcher", "splash", "admob", "vungle", "unity", "chartboost"]):
                try: details["images"][name.split('/')[-1]] = zip_obj.read(name)
                except: pass
        if lower_name.startswith("res/layout/") and lower_name.endswith(".xml"): details["layouts"].add(lower_name.split('/')[-1])

        try:
            raw_bytes = zip_obj.read(name) if info.file_size < 2 * 1024 * 1024 else zip_obj.open(name).read(2 * 1024 * 1024)
            if any(lower_name.endswith(ext) for ext in [".db", ".sqlite"]): details["db_schemas"].update(inspect_sqlite_db(raw_bytes))
            for pm in re.findall(rb'type\.googleapis\.com/[A-Za-z0-9_.-]+', raw_bytes): details["protobuf_schemas"].add(pm.decode('ascii', errors='ignore'))
            for gqm in re.findall(rb'(?:query|mutation)\s+[A-Za-z0-9_]+', raw_bytes): details["graphql_ops"].add(gqm.decode('ascii', errors='ignore'))
            for jm in re.findall(rb'Java_[A-Za-z0-9_]+', raw_bytes): details["jni_exports"].add(jm.decode('ascii', errors='ignore'))
            if lower_name.endswith(".dex"):
                for cm in re.findall(rb'L[a-zA-Z0-9_$]+/[a-zA-Z0-9_$]+;', raw_bytes)[:100]:
                    dec_cls = cm.decode('ascii', errors='ignore')
                    if not is_framework_noise(dec_cls): details["class_paths"].add(dec_cls)
            details["xor_urls"].update(check_xor_obfuscation(raw_bytes))
            file_tokens = extract_strings_from_bytes(raw_bytes)
            if lower_name.endswith(".so"):
                for token in list(file_tokens)[:300]: details["native_strings"].add(demangle_cpp_symbol(token) if token.startswith("_Z") else token)
            elif any(lower_name.endswith(ext) for ext in [".csv", ".json", ".proto", ".txt", ".dat", ".xml", ".properties"]): details["config_strings"].update(file_tokens)
            else: details["all_strings"].update(file_tokens)
            if lower_name.endswith("resources.arsc") or lower_name.endswith(".arsc"): details["ui_strings"].update(t for t in file_tokens if looks_like_ui_text(t))
            for token in file_tokens:
                t_low = token.lower()
                if "permission." in t_low: details["permissions"].add(token)
                elif "activity" in t_low or "screen" in t_low: details["activities"].add(token)
                elif "service" in t_low or "receiver" in t_low: details["services"].add(token)
                elif t_low.startswith("http"): details["endpoints"].add(token)
                elif "scheme://" in t_low or "://" in t_low: details["deep_links"].add(token)
        except: pass

def inspect_entire_bundle(file_bytes):
    details = {k: set() for k in ["files", "all_strings", "native_strings", "config_strings", "annotations", "protobuf_schemas", "graphql_ops", "jni_exports", "class_paths", "db_schemas", "xor_urls", "activities", "services", "permissions", "deep_links", "endpoints", "ui_strings", "layouts"]}
    details.update({"total_size": 0, "images": {}, "category_sizes": {}})
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z: process_zip_archive(z, details)
    except Exception as e: st.error(f"Error reading bundle: {e}")
    details["architectures"] = {re.match(r'lib/([^/]+)/', f).group(1) for f in details["files"] if re.match(r'lib/([^/]+)/', f)}
    details["locales"] = {re.search(r'values-([a-zA-Z]{2}(?:-r[A-Z]{2})?)/', f).group(1) for f in details["files"] if re.search(r'values-([a-zA-Z]{2}(?:-r[A-Z]{2})?)/', f)}
    details["signing_info"] = {f for f in details["files"] if f.lower().startswith("meta-inf/") and f.lower().endswith((".rsa", ".dsa", ".ec"))}
    details["splits"] = {re.search(r'(config\.[a-zA-Z0-9_]+|split_[a-zA-Z0-9_]+)\.apk', f).group(1) for f in details["files"] if re.search(r'(config\.[a-zA-Z0-9_]+|split_[a-zA-Z0-9_]+)\.apk', f)}
    haystacks = [t.lower() for t in details["class_paths"]] + [t.lower() for t in list(details["config_strings"])[:2000]]
    details["third_party_sdks"] = {name for name, sigs in SDK_SIGNATURES.items() if any(any(s.lower() in h for h in haystacks) for s in sigs)}
    return details

# ==================== RESTORED FULL QUICK FACTS ====================
def render_quickfacts(old_data, new_data, added_image_keys, new_data_images):
    old_mb, new_mb = round(old_data["total_size"] / (1024**2), 2), round(new_data["total_size"] / (1024**2), 2)
    new_sdks = new_data["third_party_sdks"] - old_data["third_party_sdks"]
    removed_sdks = old_data["third_party_sdks"] - new_data["third_party_sdks"]
    new_archs = new_data["architectures"] - old_data["architectures"]
    new_locales = new_data["locales"] - old_data["locales"]
    new_splits = new_data["splits"] - old_data["splits"]
    secrets_new = scan_for_secrets([new_data["all_strings"] - old_data["all_strings"], new_data["config_strings"] - old_data["config_strings"]])

    st.markdown('<div class="section-label">QUICK FACTS (NO AI)</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="tile-grid">
        <div class="tile"><div class="tile-val">{'+' if new_mb-old_mb >= 0 else ''}{round(new_mb-old_mb, 2)} MB</div><div class="tile-lbl">SIZE CHANGE</div></div>
        <div class="tile"><div class="tile-val">{len(new_data['files']) - len(old_data['files']):+d}</div><div class="tile-lbl">FILE COUNT CHANGE</div></div>
        <div class="tile"><div class="tile-val">{len(new_sdks)}</div><div class="tile-lbl">NEW SDKS</div></div>
        <div class="tile"><div class="tile-val">{len(new_data['jni_exports'] - old_data['jni_exports'])}</div><div class="tile-lbl">NEW JNI EXPORTS</div></div>
    </div>
    """, unsafe_allow_html=True)

    chips = '<div class="chip-row">'
    if not new_archs and not new_locales and not new_splits:
        chips += '<span class="chip">No new arch / locales / splits</span>'
    else:
        for a in sorted(new_archs): chips += f'<span class="chip">New arch: {sanitize(a)}</span>'
        for l in sorted(new_locales)[:5]: chips += f'<span class="chip">New locale: {sanitize(l)}</span>'
        for s in sorted(new_splits): chips += f'<span class="chip">Split: {sanitize(s)}</span>'
        
    if secrets_new: chips += '<span class="chip chip-warn">Possible exposed secrets found</span>'
    else: chips += '<span class="chip chip-ok">No hardcoded secrets matched</span>'
    chips += '</div>'
    st.markdown(chips, unsafe_allow_html=True)

    if secrets_new:
        with st.expander(f"Potential exposed secrets ({len(secrets_new)})"):
            for s in sorted(secrets_new):
                st.markdown(f'<div class="mono-block">{sanitize(s)}</div>', unsafe_allow_html=True)

    if added_image_keys:
        with st.expander("Newly Added Graphic Previews"):
            img_cols = st.columns(min(len(added_image_keys[:4]), 4))
            for idx, img_key in enumerate(added_image_keys[:4]):
                with img_cols[idx]:
                    try:
                        image = Image.open(io.BytesIO(new_data_images[img_key]))
                        st.image(image, caption=img_key[:15], width=70)
                    except: pass

    with st.expander("Third-party SDK ecosystem"):
        if new_sdks or removed_sdks or new_data["third_party_sdks"]:
            if new_sdks:
                st.markdown("**Newly added:**")
                st.markdown('<div class="chip-row">' + "".join(f'<span class="chip chip-ok">{sanitize(s)}</span>' for s in sorted(new_sdks)) + '</div>', unsafe_allow_html=True)
            if removed_sdks:
                st.markdown("**Removed:**")
                st.markdown('<div class="chip-row">' + "".join(f'<span class="chip chip-warn">{sanitize(s)}</span>' for s in sorted(removed_sdks)) + '</div>', unsafe_allow_html=True)
            st.markdown("**All SDKs detected in new build:**")
            st.markdown('<div class="chip-row">' + "".join(f'<span class="chip">{sanitize(s)}</span>' for s in sorted(new_data["third_party_sdks"])) + '</div>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="chip chip-ok">No third-party SDKs detected</span>', unsafe_allow_html=True)

    with st.expander("Size breakdown by category (new build)"):
        cats = sorted(new_data["category_sizes"].items(), key=lambda x: -x[1])
        for cat, size in cats:
            mb = round(size / (1024 * 1024), 2)
            if mb > 0.01: st.markdown(f"**{sanitize(cat)}** — {mb} MB")

    with st.expander("Signing & packaging metadata"):
        sign_new = new_data["signing_info"]
        if sign_new:
            for s in sorted(sign_new): st.markdown(f"- {sanitize(s)}")
        if new_data["architectures"]:
            st.markdown(f"**Architectures:** {', '.join(sorted(new_data['architectures']))}")

    added_ui = sorted(new_data["ui_strings"] - old_data["ui_strings"])
    removed_ui = sorted(old_data["ui_strings"] - new_data["ui_strings"])
    
    with st.expander(f"New UI Text Labels ({len(added_ui)})"):
        if added_ui or removed_ui:
            full_ui_export = f"=== ADDED UI TEXTS ({len(added_ui)}) ===\n" + "\n".join(added_ui) + f"\n\n=== REMOVED UI TEXTS ({len(removed_ui)}) ===\n" + "\n".join(removed_ui)
            st.download_button("Download Full UI Text Diff", data=full_ui_export, file_name="ui_text_diff.txt", mime="text/plain", use_container_width=True)

            ui_search = st.text_input("Search UI Texts:", placeholder="Type to filter...", key="ui_search_key")
            if ui_search.strip():
                sq = ui_search.strip().lower()
                filt_added = [s for s in added_ui if sq in s.lower()]
                filt_rem = [s for s in removed_ui if sq in s.lower()]
                for s in filt_added[:150]: st.markdown(f"- {sanitize(s)}")
                for s in filt_rem[:150]: st.markdown(f"- ~~{sanitize(s)}~~")
            else:
                for s in added_ui[:150]: st.markdown(f"- {sanitize(s)}")
        else:
            st.markdown("_No new UI text detected._")

    with st.expander("Raw string diff — unfiltered (no AI)"):
        raw_added = sorted((new_data["all_strings"] | new_data["config_strings"]) - (old_data["all_strings"] | old_data["config_strings"]))
        raw_removed = sorted((old_data["all_strings"] | old_data["config_strings"]) - (new_data["all_strings"] | new_data["config_strings"]))

        full_raw_export = f"=== ADDED ({len(raw_added)}) ===\n" + "\n".join(raw_added) + f"\n\n=== REMOVED ({len(raw_removed)}) ===\n" + "\n".join(raw_removed)
        st.download_button("Download Raw Strings Diff", data=full_raw_export, file_name="raw_strings_diff.txt", mime="text/plain", use_container_width=True)

        raw_search = st.text_input("Search Raw Strings:", placeholder="Type to filter...", key="raw_search_key")
        if raw_search.strip():
            sq_raw = raw_search.strip().lower()
            for s in [x for x in raw_added if sq_raw in x.lower()][:150]: st.markdown(f'<div class="mono-block">{sanitize(s)}</div>', unsafe_allow_html=True)
        else:
            for s in raw_added[:150]: st.markdown(f'<div class="mono-block">{sanitize(s)}</div>', unsafe_allow_html=True)

def render_standard_dashboard(report_data):
    st.markdown(f"""
    <div class="chip-row">
        <span class="chip">Size Change: <b>{report_data.get("size_diff_mb", 0.0)} MB</b></span>
        <span class="chip">New Flags: <b>{report_data.get("num_flags", 0)}</b></span>
        <span class="chip">New JNI: <b>{report_data.get("num_jni", 0)}</b></span>
    </div>
    <div class="report-card" style="background-color: #F3EDF7; border-left: 4px solid #6750A4;"><div class="report-card-title">AI Analysis & Executive Summary</div><div class="report-card-body">{sanitize(report_data.get("summary", ""))}</div></div>
    <div class="report-card" style="background-color: #FFD8E4; border-left: 4px solid #B12B58;"><div class="report-card-title">Unreleased Feature Blueprints</div><div class="report-card-body">{sanitize(str(report_data.get("blueprints", "")))}<div class="cmd-box">{sanitize(report_data.get("command", ""))}</div></div></div>
    <div class="report-card" style="background-color: #FFF3E0; border-left: 4px solid #E8A33D;"><div class="report-card-title">Security & Packaging Assessment</div><div class="report-card-body">{sanitize(report_data.get("security", ""))}</div></div>
    """, unsafe_allow_html=True)

def render_hunter_dashboard(hunter_data):
    st.markdown(f'<div class="hunter-card" style="border-left: 4px solid #D0BCFF;"><div class="hunter-title">Investigative Summary</div><div style="font-size: 13.5px; color: #E6E1E5;">{sanitize(hunter_data.get("summary", ""))}</div></div>', unsafe_allow_html=True)
    
    for idx, feat in enumerate(hunter_data.get("features", [])):
        feat_name = feat.get("name", f"Feature {idx+1}")
        cmd = feat.get("activation", "")
        
        st.markdown(f'''
        <div class="hunter-card">
            <div class="hunter-title">{sanitize(feat_name)}</div>
            <div class="hunter-evidence"><b>Evidence:</b><br>{sanitize(feat.get("evidence", ""))}</div>
            <div class="hunter-cmd">$ {sanitize(cmd)}</div>
        </div>
        ''', unsafe_allow_html=True)

# ==================== MAIN UI FLOW ====================
if st.session_state.report_data or st.session_state.hunter_data:
    if st.session_state.quickfacts:
        render_quickfacts(st.session_state.quickfacts[0], st.session_state.quickfacts[1], st.session_state.added_image_keys, st.session_state.new_data_images)
    
    if st.session_state.scan_mode == "hunter":
        st.markdown('<div class="section-label" style="color:#6750A4;">FEATURE INTEL REPORT</div>', unsafe_allow_html=True)
        render_hunter_dashboard(st.session_state.hunter_data)
    else:
        st.markdown('<div class="section-label">AI TEARDOWN REPORT</div>', unsafe_allow_html=True)
        render_standard_dashboard(st.session_state.report_data)

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
        
    if st.button("Start New Scan", use_container_width=True):
        st.session_state.report_data = st.session_state.hunter_data = st.session_state.scan_mode = None
        st.session_state.jadx_ready = False
        st.session_state.jadx_zip_bytes = None
        st.rerun()

else:
    old_file = st.file_uploader("Old Version (.apk, .aab, .apkm)", type=["apk", "aab", "xapk", "apks", "apkm", "zip"], accept_multiple_files=False)
    new_file = st.file_uploader("New Version (.apk, .aab, .apkm)", type=["apk", "aab", "xapk", "apks", "apkm", "zip"], accept_multiple_files=False)
    run_standard = st.button("Standard Deep Scan", use_container_width=True)
    st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
    run_hunter = st.button("Investigative Feature Hunt", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if run_standard or run_hunter:
        if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
            st.error("Missing GROQ_API_KEY")
        elif not old_file or not new_file:
            st.error("Please upload both files.")
        else:
            st.session_state.scan_mode = "hunter" if run_hunter else "standard"
            
            st.session_state.new_file_bytes = new_file.read()
            st.session_state.new_file_name = new_file.name
            old_file.seek(0)
            new_file.seek(0)

            # RENDER RADAR ANIMATION IMMEDIATELY
            scanner = st.empty()
            scanner.markdown("""
            <div class="scanner-box">
                <div class="pulse-container">
                    <div class="radar-ring"></div>
                    <div class="radar-core"></div>
                </div>
                <div style="font-weight: 800; font-size: 16px; color: #21005D;">Decompressing Archives & Native JNI Bridges</div>
                <div style="font-size: 13px; color: #49454F; margin-top: 4px;">Demangling C++ symbols, mapping GraphQL & ProtoBufs...</div>
            </div>
            """, unsafe_allow_html=True)
            
            time.sleep(0.1)

            old_data = inspect_entire_bundle(old_file.read())
            new_data = inspect_entire_bundle(st.session_state.new_file_bytes)
            st.session_state.quickfacts = (old_data, new_data)

            scanner.markdown("""
            <div class="scanner-box">
                <div class="pulse-container">
                    <div class="radar-ring" style="border-color: #D0BCFF;"></div>
                    <div class="radar-core" style="background: #D0BCFF;"></div>
                </div>
                <div style="font-weight: 800; font-size: 16px; color: #21005D;">Synthesizing AI Feature Intel</div>
                <div style="font-size: 13px; color: #49454F; margin-top: 4px;">Correlating UI text, layout schemas, and flags...</div>
            </div>
            """, unsafe_allow_html=True)
            time.sleep(0.1)

            diff_summary = f"""
            SIZE CHANGE: {round(new_data["total_size"]/(1024**2) - old_data["total_size"]/(1024**2), 2)} MB
            NEW LAYOUTS: {sorted(list(new_data["layouts"] - old_data["layouts"]))[:25]}
            NEW UI TEXT: {sorted(list(new_data["ui_strings"] - old_data["ui_strings"]))[:35]}
            NEW PERMISSIONS: {sorted(list(new_data["permissions"] - old_data["permissions"]))[:10]}
            """
            
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            
            if run_hunter:
                prompt = f"""
                You are an investigative mobile app software journalist finding hidden features in an APK diff.
                Correlate the provided layouts, UI text, and feature flags to deduce unreleased features.
                Output ONLY valid JSON. NEVER use double quotes (") inside JSON text values. Use single quotes (') instead.

                JSON Schema required:
                {{
                  "summary": "3-4 concise narrative sentences summarizing the unreleased features found.",
                  "features": [
                    {{
                      "name": "Feature Name",
                      "evidence": "State the flag, string, and layout that prove this.",
                      "activation": "adb shell dumpsys package | grep -i feature_flag"
                    }}
                  ]
                }}

                RAW DATA:
                {diff_summary}
                """
            else:
                prompt = f"""
                You are a lead mobile software investigator analyzing an APK diff.
                Output ONLY valid JSON. NEVER use double quotes (") inside JSON text values. Use single quotes (') instead.

                JSON Schema required:
                {{
                  "summary": "3-4 concise narrative sentences explaining the technical changes.",
                  "blueprints": "Concrete feature predictions based strictly on the data.",
                  "command": "An adb terminal grep command.",
                  "security": "Assessment of risks."
                }}

                RAW DATA:
                {diff_summary}
                """

            try:
                # LOCKED AT TEMPERATURE 0.0 FOR DETERMINISTIC AI OUTPUT
                comp = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                res = json.loads(clean_json_response(comp.choices[0].message.content.strip()))
                if run_hunter:
                    st.session_state.hunter_data = res
                else:
                    res["size_diff_mb"] = round(new_data["total_size"]/(1024**2) - old_data["total_size"]/(1024**2), 2)
                    st.session_state.report_data = res
                scanner.empty()
                st.rerun()
            except Exception as e:
                scanner.empty()
                st.error(f"Analysis error: {e}")
