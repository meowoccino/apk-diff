import streamlit as st
import zipfile
import io
import re
import tempfile
import os
import subprocess
import urllib.request
import shutil
import html
import json
import shlex
from PIL import Image
from groq import Groq

# ==================== PAGE SETUP ====================
st.set_page_config(page_title="apk-diff pro", layout="centered")

# ==================== UTILITY & SANITIZATION ====================
def sanitize(text):
    if not text:
        return ""
    return html.escape(str(text)).replace("$", r"\$")

def clean_json_response(raw_str):
    cleaned = re.sub(r"^```json\s*", "", raw_str, flags=re.MULTILINE)
    cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()

def is_valid_feature_flag(s):
    if not s or " " in s or len(s) > 80:
        return False
    s_low = s.lower()
    noise_words = [
        "cannot build keyset", "configuration is required", "exception",
        "builder#setconfiguration", "lopt;", "regularbuttonconfig", "scaleconfig"
    ]
    if any(n in s_low for n in noise_words):
        return False
    return any(k in s_low for k in ['flag', 'enable', 'config', 'opt', 'toggle', 'experiment', 'beta', 'gating'])

def fix_adb_command_syntax(cmd, target_pkg):
    if not target_pkg or target_pkg == "com.unknown.app":
        target_pkg = "com.android.vending"
        
    clean = cmd.replace("$", "").strip()
    for placeholder in ["PACKAGE_NAME", "com.example.app", "com.unknown.app"]:
        clean = clean.replace(placeholder, target_pkg)
        
    if " -n " in clean:
        prefix, intent_target = clean.split(" -n ", 1)
        intent_target = intent_target.strip()
        if "/" not in intent_target:
            if intent_target.startswith(target_pkg):
                act = intent_target[len(target_pkg):].strip(".")
                clean = f"{prefix} -n {target_pkg}/.{act}"
            else:
                clean = f"{prefix} -n {target_pkg}/{intent_target}"
    return clean

def is_local_adb_available():
    if not shutil.which("adb"):
        return False
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=2)
        lines = [l for l in res.stdout.strip().split("\n") if l.endswith("\tdevice")]
        return len(lines) > 0
    except Exception:
        return False

# ==================== TIMELINE CSS & SVG STYLING ====================
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

    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stStatusWidget"], [data-testid="manage-app-button"],
    [data-testid="stAppDeployButton"], header, footer {
        display: none !important;
        visibility: hidden !important;
    }

    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .timeline { position: relative; padding-left: 28px; margin-top: 16px; }
    .timeline::before { content: ''; position: absolute; top: 8px; left: 11px; height: calc(100% - 16px); width: 2px; background: #CBD5E1; }
    
    .node { position: relative; margin-bottom: 20px; }
    .node-icon {
        position: absolute; left: -28px; top: 0; width: 24px; height: 24px;
        background: #FFFFFF; border: 2px solid #2563EB; border-radius: 50%;
        display: flex; align-items: center; justify-content: center; color: #2563EB;
        z-index: 2; box-shadow: 0 0 0 4px #F8FAFC;
    }
    .node-icon.ai { background: #2563EB; color: #FFFFFF; }

    .timeline-card { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .node-title { font-size: 15px; font-weight: 800; color: #1E293B; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
    .node-sub { font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }

    div[data-testid="stFileUploader"], div[data-testid="stTextInput"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 8px !important;
        margin-bottom: 8px;
    }
    div[data-testid="stFileUploader"] small { display: none !important; }

    div.stButton > button {
        background: #2563EB !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2) !important;
        min-height: 40px !important;
        width: 100%;
    }

    .chip-row { display: flex; gap: 6px; flex-wrap: wrap; margin: 6px 0 10px 0; }
    .chip { background: #F1F5F9; color: #1E293B; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 6px; border: 1px solid #E2E8F0; }
    .chip-warn { background: #FEE2E2; color: #991B1B; border-color: #FECACA; }
    .chip-ok { background: #DCFCE7; color: #166534; border-color: #BBF7D0; }

    .mono-block {
        background-color: #0F172A; color: #E2E8F0;
        border-radius: 6px; padding: 8px 10px;
        font-family: monospace; font-size: 11px;
        word-break: break-all; margin-top: 4px; margin-bottom: 4px;
    }
    .mono-add { color: #4ADE80; }
    .mono-guess { color: #94A3B8; font-style: italic; }

    [data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        margin-bottom: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="display: flex; align-items: center; gap: 12px; margin-top: 6px; margin-bottom: 12px;">
    <div style="background: #2563EB; padding: 8px; border-radius: 10px; color: white; display: flex; align-items: center; justify-content: center;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="width: 22px; height: 22px;">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
    </div>
    <div>
        <h1 style="font-size: 19px; font-weight: 800; margin:0;">apk-diff pro</h1>
        <p style="font-size: 12px; color: #64748B; margin:0;">Unified Reverse Engineering Intelligence</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ==================== JADX DECOMPILER SETUP ====================
def setup_jadx():
    if not shutil.which("java"):
        raise RuntimeError("Java (OpenJDK) is not installed on Streamlit Cloud. Please add 'default-jre' to your repository's packages.txt file.")

    if not os.path.exists("jadx"):
        with st.spinner("Preparing JADX extraction engine..."):
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
            res = subprocess.run(["jadx/bin/jadx", "-d", out_dir, "-r", "--show-bad-code", apk_path], capture_output=True, text=True, timeout=300)
            if res.returncode != 0 and not os.listdir(out_dir):
                st.error(f"JADX failed to decompile APK: {res.stderr[:200]}")
                return None
            
        zip_base_path = os.path.join(tempfile.gettempdir(), f"{filename}_source")
        archive_path = shutil.make_archive(zip_base_path, 'zip', out_dir)
        
        with open(archive_path, "rb") as f:
            return f.read()
    except Exception as e:
        st.error(f"Extraction encountered an issue: {e}")
        return None

# ==================== SESSION STATE ====================
for key, default in [
    ("hunter_data", None),
    ("added_image_keys", []),
    ("modified_image_keys", []),
    ("old_data_images", {}),
    ("new_data_images", {}),
    ("quickfacts", None),
    ("jadx_ready", False),
    ("jadx_zip_bytes", None),
    ("target_pkg", "")
]:
    if key not in st.session_state:
        st.session_state[key] = default

NOISE_PATTERNS = [
    "androidx/", "com/google/android/", "kotlin/", "java/", "javax/",
    "android/support/", "org/apache/", "com/facebook/", "io/reactivex/",
    "Ljava/", "Lkotlin/", "Landroid/", "Landroidx/", "webrtc", "googleusercontent"
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
}

def is_framework_noise(token):
    token_lower = token.lower()
    return any(noise in token_lower for noise in NOISE_PATTERNS)

def clean_ui_string(s):
    if not s:
        return ""
    return re.sub(r'^[#$@%!&\*\-]+', '', s).strip()

def looks_like_ui_text(raw_s):
    s = clean_ui_string(raw_s)
    if not (2 <= len(s) <= 140): return False
    if "/" in s or "\\" in s: return False
    if any(sub in s.lower() for sub in ("://", ".png", ".jpg", ".webp", ".xml", ".so", ".dex", ".ttf", "androidx", "kotlin.", "java.", "com.google")): return False
    has_space = " " in s
    has_lower = any(c.islower() for c in s)
    has_letter = any(c.isalpha() for c in s)
    if not has_letter: return False
    return has_space or has_lower or "_" in s

def extract_strings_from_bytes(raw_bytes):
    strings = set()
    utf8_matches = re.findall(rb'[\x20-\x7E\xC2-\xDF\xE0-\xEF\xF0-\xF4\x80-\xBF]{5,}', raw_bytes)
    for m in utf8_matches:
        try:
            decoded = m.decode('utf-8').strip()
            if len(decoded) > 4 and not re.match(r'^[A-Za-z0-9+/=]{15,}$', decoded) and not is_framework_noise(decoded):
                strings.add(decoded)
        except UnicodeDecodeError:
            pass
            
    utf16_matches = re.findall(rb'(?:[\x20-\x7E]\x00){4,}', raw_bytes)
    for m in utf16_matches:
        try:
            decoded = m.decode('utf-16le').strip()
            if len(decoded) > 3 and not is_framework_noise(decoded):
                strings.add(decoded)
        except UnicodeDecodeError:
            pass
            
    return strings

def categorize_file(lower_name):
    if lower_name.endswith(".dex"): return "Dalvik Bytecode (DEX)"
    if lower_name.endswith(".so"): return "Native Libraries (.so)"
    if lower_name.endswith((".png", ".webp", ".jpg", ".jpeg", ".gif")): return "Images"
    if lower_name.endswith(".arsc"): return "Compiled Resources (ARSC)"
    if lower_name.endswith((".db", ".sqlite")): return "Databases"
    if lower_name.endswith(".xml"): return "XML Resources"
    if lower_name.startswith("meta-inf/"): return "Signing / Metadata"
    return "Other"

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
            if not any(ignore in lower_name for ignore in ["icon", "launcher", "splash", "admob", "vungle", "unity"]):
                try: details["images"][name.split('/')[-1]] = zip_obj.read(name)
                except Exception: pass

        if lower_name.startswith("res/layout/") and lower_name.endswith(".xml"):
            details["layouts"].add(lower_name.split('/')[-1])

        try:
            raw_bytes = zip_obj.read(name) if info.file_size < 10 * 1024 * 1024 else zip_obj.open(name).read(5 * 1024 * 1024)

            if lower_name == "androidmanifest.xml":
                manifest_tokens = extract_strings_from_bytes(raw_bytes)
                for tok in manifest_tokens:
                    if re.match(r'^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$', tok) and not any(tok.startswith(p) for p in ["android.", "androidx.", "schemas.", "http"]):
                        if tok.count('.') >= 2:
                            details["manifest_packages"].add(tok)

            proto_matches = re.findall(rb'type\.googleapis\.com/[A-Za-z0-9_.-]+', raw_bytes)
            for pm in proto_matches: details["protobuf_schemas"].add(pm.decode('ascii', errors='ignore'))

            graphql_matches = re.findall(rb'(?:query|mutation)\s+[A-Za-z0-9_]+', raw_bytes)
            for gqm in graphql_matches: details["graphql_ops"].add(gqm.decode('ascii', errors='ignore'))

            jni_matches = re.findall(rb'Java_[A-Za-z0-9_]+', raw_bytes)
            for jm in jni_matches: details["jni_exports"].add(jm.decode('ascii', errors='ignore'))

            if lower_name.endswith(".dex"):
                class_matches = re.findall(rb'L[a-zA-Z0-9_$]+/[a-zA-Z0-9_$]+;', raw_bytes)
                for cm in class_matches[:250]:
                    decoded_cls = cm.decode('ascii', errors='ignore')
                    if not is_framework_noise(decoded_cls): 
                        formatted_cls = decoded_cls.lstrip('L').rstrip(';').replace('/', '.')
                        details["class_paths"].add(formatted_cls)

            file_tokens = extract_strings_from_bytes(raw_bytes)
            if lower_name.endswith(".so"):
                details["native_strings"].update(file_tokens)
            elif any(lower_name.endswith(ext) for ext in [".csv", ".json", ".proto", ".txt", ".xml", ".properties"]):
                details["config_strings"].update(file_tokens)
            else:
                details["all_strings"].update(file_tokens)

            if lower_name.endswith("resources.arsc") or lower_name.endswith(".arsc"):
                details["ui_strings"].update(clean_ui_string(t) for t in file_tokens if looks_like_ui_text(t))

            for token in file_tokens:
                clean_token = re.sub(r'^[a-zA-Z0-9]+http', 'http', token)
                clean_lower = clean_token.lower()
                if "permission." in clean_lower: details["permissions"].add(clean_token)
                elif ("activity" in clean_lower or "screen" in clean_lower) and "." in clean_token: details["activities"].add(clean_token)
                elif clean_lower.startswith("http://") or clean_lower.startswith("https://"): details["endpoints"].add(clean_token)
                elif "scheme://" in clean_lower or "://" in clean_lower: details["deep_links"].add(clean_token)
        except Exception: pass

def inspect_entire_bundle(file_bytes):
    details = {
        "files": set(), "total_size": 0, "all_strings": set(), "native_strings": set(), "config_strings": set(),
        "protobuf_schemas": set(), "graphql_ops": set(), "jni_exports": set(), "class_paths": set(),
        "activities": set(), "permissions": set(), "deep_links": set(), "endpoints": set(),
        "images": {}, "category_sizes": {}, "ui_strings": set(), "layouts": set(), "manifest_packages": set(),
        "architectures": set(), "locales": set(), "splits": set(), "third_party_sdks": set()
    }
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            process_zip_archive(z, details)
    except Exception as e:
        st.error(f"Error reading package bundle: {e}")

    pkg_candidates = list(details["manifest_packages"])
    if pkg_candidates:
        pkg_candidates.sort(key=lambda x: len(x.split('.')))
        details["package_name"] = pkg_candidates[0]
    else:
        details["package_name"] = "com.android.vending"

    return details

def generate_markdown_report(hunter_data):
    lines = ["# APK Leak & Feature Intelligence Report\n"]
    if hunter_data:
        lines.append("## Executive Summary")
        lines.append(f"{hunter_data.get('summary', '')}\n")
        
        r8_guesses = hunter_data.get("r8_guesses", [])
        if r8_guesses:
            lines.append("## R8 Class Deobfuscation Guesses")
            for g in r8_guesses: lines.append(f"- `{g}`")
            lines.append("")
            
        lines.append("## Unreleased Feature Intelligence")
        for f in hunter_data.get("features", []):
            lines.append(f"### {f.get('name', 'Unknown Feature')}")
            lines.append(f"**Evidence:** {f.get('evidence', '')}")
            lines.append(f"**Security Gating:** Exported Component ({f.get('security_risk', 'Normal')})")
            lines.append(f"**Activation Intent:**\n```bash\n{f.get('activation', '')}\n```\n")
            
    return "\n".join(lines)

# ==================== FULLSCREEN TIMELINE REPORT VIEW ====================
if st.session_state.hunter_data:
    old_data, new_data = st.session_state.quickfacts
    hunter_data = st.session_state.hunter_data

    st.markdown("<div class='timeline'>", unsafe_allow_html=True)

    # NODE 1: TARGET BASELINE
    pkg_str = sanitize(st.session_state.target_pkg)
    size_mb = (new_data['total_size'] - old_data['total_size']) / (1024*1024)
    st.markdown(f"""
    <div class="node">
        <div class="node-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
        </div>
        <div class="timeline-card">
            <div class="node-title">Package Baseline & Target</div>
            <div class="chip-row">
                <span class="chip chip-ok">Target: <b>{pkg_str}</b></span>
                <span class="chip">Size Change: <b>{size_mb:+.2f} MB</b></span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # NODE 2: SDK ECOSYSTEM
    new_sdks = new_data["third_party_sdks"] - old_data["third_party_sdks"]
    st.markdown("""
    <div class="node">
        <div class="node-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
        </div>
        <div class="timeline-card">
            <div class="node-title">SDK Ecosystem & Shifts</div>
            <div class="chip-row">
    """, unsafe_allow_html=True)
    if new_sdks:
        for sdk in sorted(new_sdks): st.markdown(f'<span class="chip chip-ok">+ {sanitize(sdk)}</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="chip">No new third-party SDKs added</span>', unsafe_allow_html=True)
    st.markdown("</div></div></div>", unsafe_allow_html=True)

    # NODE 3: ASSET DIFFS
    if st.session_state.added_image_keys or st.session_state.modified_image_keys:
        st.markdown("""
        <div class="node">
            <div class="node-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
            </div>
            <div class="timeline-card">
                <div class="node-title">Asset & Graphic Diffs</div>
        """, unsafe_allow_html=True)
        if st.session_state.modified_image_keys:
            st.markdown("<div class='node-sub'>Modified Images (Side-by-Side)</div>", unsafe_allow_html=True)
            for img_key in st.session_state.modified_image_keys[:2]:
                c1, c2 = st.columns(2)
                with c1: st.image(Image.open(io.BytesIO(st.session_state.old_data_images[img_key])), caption=f"OLD: {img_key[:12]}", width=60)
                with c2: st.image(Image.open(io.BytesIO(st.session_state.new_data_images[img_key])), caption=f"NEW: {img_key[:12]}", width=60)
        st.markdown("</div></div>", unsafe_allow_html=True)

    # NODE 4: CODEBASE & DEOBFUSCATION
    st.markdown("""
    <div class="node">
        <div class="node-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
        </div>
        <div class="timeline-card">
            <div class="node-title">Codebase & Smali Logic</div>
    """, unsafe_allow_html=True)
    r8_guesses = hunter_data.get("r8_guesses", [])
    if r8_guesses:
        st.markdown("<div class='node-sub'>R8 Class Deobfuscation Guesses</div>", unsafe_allow_html=True)
        for g in r8_guesses[:5]: st.markdown(f'<div class="mono-block mono-guess">{sanitize(g)}</div>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

    # NODE 5: STRINGS & SEARCH
    added_ui = sorted(new_data["ui_strings"] - old_data["ui_strings"])
    st.markdown("""
    <div class="node">
        <div class="node-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        </div>
        <div class="timeline-card">
            <div class="node-title">Categorized String Diff</div>
    """, unsafe_allow_html=True)

    if added_ui:
        st.download_button(
            label="Download UI Text Diff (.txt)",
            data="\n".join(added_ui),
            file_name="ui_text_diff.txt",
            mime="text/plain",
            use_container_width=True
        )
        ui_query = st.text_input("Filter UI Texts:", placeholder="Type to filter...", key="ui_filter")
        filtered_ui = [s for s in added_ui if ui_query.lower() in s.lower()] if ui_query else added_ui
        for s in filtered_ui[:100]: st.markdown(f'<div class="mono-block mono-add">+ {sanitize(s)}</div>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

    # NODE 6: AI INTEL & BLUEPRINTS
    ai_summary_str = sanitize(hunter_data.get("summary", ""))
    st.markdown(f"""
    <div class="node">
        <div class="node-icon ai">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
        </div>
        <div class="timeline-card" style="border-left: 4px solid #2563EB;">
            <div class="node-title">AI Feature Intelligence</div>
            <p style="font-size: 13px; margin-bottom: 12px;">{ai_summary_str}</p>
    """, unsafe_allow_html=True)

    for idx, feat in enumerate(hunter_data.get("features", [])):
        name = sanitize(feat.get("name", "Feature"))
        evidence = sanitize(feat.get("evidence", ""))
        raw_cmd = feat.get("activation", "")
        clean_cmd = fix_adb_command_syntax(raw_cmd, st.session_state.target_pkg)
        display_cmd = f"adb {clean_cmd.replace('adb ', '')}"

        st.markdown(f"""
        <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px; margin-bottom: 10px;">
            <div style="font-weight:700; font-size:13px; color:#1E293B;">{name}</div>
            <div style="font-size:11px; color:#64748B; margin-top:2px;"><b>Evidence:</b> {evidence}</div>
            <div class="mono-block" style="margin-top:6px;">{sanitize(display_cmd)}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div></div></div>", unsafe_allow_html=True)

    # ACTIONS
    report_md = generate_markdown_report(hunter_data)
    st.download_button(
        label="Download Leak Report (.md)",
        data=report_md,
        file_name=f"{st.session_state.target_pkg}_leak_report.md",
        mime="text/markdown",
        use_container_width=True
    )

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
        st.session_state.hunter_data = None
        st.session_state.added_image_keys = []
        st.session_state.modified_image_keys = []
        st.session_state.new_data_images = {}
        st.session_state.old_data_images = {}
        st.session_state.quickfacts = None
        st.session_state.jadx_ready = False
        st.session_state.jadx_zip_bytes = None
        st.session_state.target_pkg = ""
        st.rerun()

# ==================== MAIN UNIFIED INPUT VIEW ====================
else:
    play_store_url = st.text_input("Play Store Baseline URL (Optional)", value="", placeholder="https://play.google.com/store/apps/details?id=...")
    old_file = st.file_uploader("Old Baseline Package (.apk, .aab, .xapk)", type=["apk", "aab", "xapk", "apks", "apkm", "zip"], accept_multiple_files=False)
    new_file = st.file_uploader("New Target Package (.apk, .aab, .xapk)", type=["apk", "aab", "xapk", "apks", "apkm", "zip"], accept_multiple_files=False)

    user_pkg_input = st.text_input("Target Package Name (Auto-detected if blank)", value="", placeholder="e.g. com.discord or com.spotify")

    if st.button("Run Feature Hunt", use_container_width=True):
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
            scanner_placeholder.info("Decompressing package archives & mapping bytecode...")

            old_bytes = old_file.read()
            new_bytes = st.session_state.new_file_bytes

            old_data = inspect_entire_bundle(old_bytes)
            new_data = inspect_entire_bundle(new_bytes)
            st.session_state.quickfacts = (old_data, new_data)

            final_pkg_name = user_pkg_input.strip() if user_pkg_input.strip() else new_data.get("package_name", "com.android.vending")
            st.session_state.target_pkg = final_pkg_name

            added_native = list(new_data["native_strings"] - old_data["native_strings"])
            added_configs = list(new_data["config_strings"] - old_data["config_strings"])
            added_general = list(new_data["all_strings"] - old_data["all_strings"])
            
            combined_diffs = added_native[:300] + added_configs[:300] + added_general[:300]
            feature_toggles = [t for t in combined_diffs if is_valid_feature_flag(t)]

            added_activities = list(new_data["activities"] - old_data["activities"])
            added_deep_links = list(new_data["deep_links"] - old_data["deep_links"])
            added_layouts = list(new_data["layouts"] - old_data["layouts"])
            
            raw_ui = list(new_data["ui_strings"] - old_data["ui_strings"])
            added_ui_strings = [s for s in raw_ui if len(s) > 12]

            st.session_state.added_image_keys = [k for k in new_data["images"].keys() if k not in old_data["images"]]
            st.session_state.modified_image_keys = [k for k in new_data["images"].keys() if k in old_data["images"] and new_data["images"][k] != old_data["images"][k]]
            st.session_state.new_data_images = new_data["images"]
            st.session_state.old_data_images = old_data["images"]

            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            scanner_placeholder.info("Synthesizing unified AI feature intelligence...")

            hunter_summary = f"""
            TARGET APP PACKAGE NAME: {st.session_state.target_pkg}
            NEW ACTIVITIES: {added_activities[:100]}
            NEW DEEP LINKS: {added_deep_links[:100]}
            NEW XML LAYOUTS: {added_layouts[:150]}
            NEW UI TEXT: {added_ui_strings[:200]}
            TIGHTENED FEATURE FLAGS: {feature_toggles[:120]}
            """

            prompt = f"""
            You are a lead mobile reverse engineering analyst reviewing an APK diff.
            CRITICAL INSTRUCTIONS:
            1. Focus STRICTLY on finding new Exported Activities, Deep Links, and feature flag correlations.
            2. Infer likely R8 obfuscated class mappings (e.g. 'a.b.c -> androidx.fragment.app.Fragment') if present.
            3. Do NOT limit your finding count artificially; extract ALL notable unreleased features.
            4. For Activity commands, specify full activity path using target package string '{st.session_state.target_pkg}'. Include intent extras (--ez / --es) if needed.
            Respond ONLY in valid JSON format with double quotes properly escaped.

            JSON Schema required:
            {{
              "summary": "3-4 concise narrative sentences summarizing the unreleased features.",
              "r8_guesses": ["a.b.c -> likely_class_purpose"],
              "features": [
                {{
                  "name": "Feature Name",
                  "evidence": "Full activity, deep link, or layout that proves this.",
                  "security_risk": "Exported True / False",
                  "activation": "adb shell am start -n {st.session_state.target_pkg}/FULL_CLASS_NAME"
                }}
              ]
            }}

            RAW DATA:
            {hunter_summary}
            """

            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=2000,
                    response_format={"type": "json_object"},
                )
                raw_res = completion.choices[0].message.content.strip()
                cleaned = clean_json_response(raw_res)
                
                st.session_state.hunter_data = json.loads(cleaned)
                scanner_placeholder.empty()
                st.rerun()
            except Exception as e:
                scanner_placeholder.empty()
                st.error(f"Analysis error: {e}")
