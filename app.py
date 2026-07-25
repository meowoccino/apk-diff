import streamlit as st
import zipfile
import io
import re
import sqlite3
import tempfile
import ctypes
from collections import defaultdict
from PIL import Image
from groq import Groq

# ==================== PAGE SETUP ====================
st.set_page_config(page_title="APK Teardown Studio", page_icon="⚡", layout="centered")

# ==================== MATERIAL DESIGN 3 — MOBILE-FIRST STYLING ====================
st.markdown("""
<style>
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        padding-top: 0rem !important;
        margin-top: 0rem !important;
    }

    .main .block-container {
        padding-top: 0.2rem !important;
        padding-bottom: 3rem !important;
        padding-left: 0.9rem !important;
        padding-right: 0.9rem !important;
        max-width: 480px !important;
    }

    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    [data-testid="manage-app-button"],
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
        background-color: #FEF7FF;
        color: #1D1B20;
        font-family: 'Roboto', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ---- Hero header ---- */
    .hero-card {
        background: linear-gradient(135deg, #F3EDF7 0%, #EADDFF 100%);
        border: 1px solid #E7E0EC;
        border-radius: 22px;
        padding: 16px 16px 14px 16px;
        margin-top: 4px;
        margin-bottom: 14px;
    }
    .hero-title-row { display: flex; align-items: center; gap: 10px; }
    .icon-badge {
        background-color: #6750A4;
        color: #fff;
        width: 38px; height: 38px;
        border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
        box-shadow: 0 2px 8px rgba(103,80,164,0.35);
    }
    .hero-title { font-size: 19px; font-weight: 800; color: #1D1B20; line-height: 1.15; }
    .hero-sub { font-size: 12.5px; color: #49454F; line-height: 1.4; margin-top: 6px; }
    .hero-pillrow { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
    .hero-pill {
        background: rgba(255,255,255,0.6);
        color: #21005D;
        font-size: 10.5px; font-weight: 700;
        padding: 3px 9px; border-radius: 100px;
        border: 1px solid rgba(103,80,164,0.25);
    }

    /* ---- Section label ---- */
    .section-label {
        font-size: 11px; font-weight: 800; letter-spacing: 0.08em;
        color: #6750A4; text-transform: uppercase;
        margin: 18px 2px 8px 2px;
    }

    /* ---- File upload slots ---- */
    div[data-testid="stFileUploader"] {
        background-color: #F3EDF7 !important;
        border: 1.5px dashed #938F99 !important;
        border-radius: 16px !important;
        padding: 6px !important;
    }

    /* ---- Checkboxes / toggles row ---- */
    div[data-testid="stCheckbox"] label p { font-size: 12.5px !important; color: #49454F; }

    /* ---- Primary MD3 button ---- */
    div.stButton > button {
        background: #6750A4 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 100px !important;
        padding: 13px 20px !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        box-shadow: 0 3px 10px rgba(103, 80, 164, 0.3) !important;
        transition: all 0.15s ease-in-out !important;
        margin-top: 10px;
        width: 100%;
    }
    div.stButton > button:hover, div.stButton > button:active {
        background: #503E81 !important;
        transform: translateY(-1px) !important;
    }

    /* ---- Scanner / progress card ---- */
    .scanner-box {
        background: #1D1B20;
        color: #E6E1E5;
        padding: 26px 16px;
        border-radius: 24px;
        text-align: center;
        margin-top: 10px;
        margin-bottom: 16px;
        border: 1px solid #49454F;
    }
    .radar-ring {
        width: 42px; height: 42px;
        margin: 0 auto 12px auto;
        border: 3px solid #D0BCFF;
        border-top-color: transparent;
        border-radius: 50%;
        animation: spin 1s infinite linear;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

    /* ---- Quick-fact metric tiles (native, non-AI) ---- */
    .tile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
    .tile {
        background: #F7F2FA;
        border: 1px solid #E7E0EC;
        border-radius: 14px;
        padding: 10px 12px;
    }
    .tile-val { font-size: 17px; font-weight: 800; color: #21005D; }
    .tile-lbl { font-size: 10.5px; color: #6F6A76; font-weight: 600; margin-top: 1px; }

    .chip-row { display: flex; gap: 6px; flex-wrap: wrap; margin: 6px 0 4px 0; }
    .chip {
        background: #E8DEF8; color: #21005D;
        font-size: 10.5px; font-weight: 700;
        padding: 4px 10px; border-radius: 100px;
    }
    .chip-warn { background: #FFDAD6; color: #410E0B; }
    .chip-ok { background: #D2F4D3; color: #0B3B12; }

    /* ---- Tabs styling ---- */
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] {
        font-size: 12.5px !important;
        font-weight: 700 !important;
        padding: 8px 10px !important;
        border-radius: 10px 10px 0 0 !important;
    }

    .mono-block {
        background-color: #1D1B20; color: #E6E1E5;
        padding: 9px 12px; border-radius: 8px;
        font-family: 'SFMono-Regular', Consolas, monospace;
        font-size: 11px; word-break: break-all;
        margin-top: 4px; margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ==================== SESSION STATE ====================
for key, default in [
    ("report_html", None),
    ("added_image_keys", []),
    ("new_data_images", {}),
    ("quickfacts", None),
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
    "WorkManager (background jobs)": ["androidx/work"],
    "ExoPlayer / Media3": ["google/android/exoplayer", "androidx/media3"],
    "gRPC": ["io/grpc"],
    "Retrofit": ["retrofit2"],
    "OkHttp": ["okhttp3"],
    "Room (local DB)": ["androidx/room"],
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
    """Heuristic filter to separate human-readable UI copy (labels, titles,
    error messages, resource keys) from paths / class descriptors that also
    live in the same binary string pool inside resources.arsc."""
    if not (2 <= len(s) <= 140):
        return False
    if "/" in s or "\\" in s:
        return False
    if any(sub in s for sub in UI_TEXT_SKIP_SUBSTR):
        return False
    has_space = " " in s
    has_lower = any(c.islower() for c in s)
    has_letter = any(c.isalpha() for c in s)
    if not has_letter:
        return False
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
                    if res:
                        return res.decode('utf-8', errors='ignore')
            except Exception:
                continue
    except Exception:
        pass
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
                if tbl and not tbl.startswith("sqlite_"):
                    schema_info.add(f"Table: {tbl}")
            conn.close()
    except Exception:
        pass
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


def categorize_file(lower_name):
    if lower_name.endswith(".dex"):
        return "Dalvik Bytecode (DEX)"
    if lower_name.endswith(".so"):
        return "Native Libraries (.so)"
    if lower_name.endswith((".png", ".webp", ".jpg", ".jpeg", ".gif")):
        return "Images"
    if lower_name.endswith(".arsc"):
        return "Compiled Resources (ARSC)"
    if lower_name.endswith((".db", ".sqlite")):
        return "Databases"
    if lower_name.endswith((".ttf", ".otf")):
        return "Fonts"
    if lower_name.endswith(".xml"):
        return "XML Resources"
    if lower_name.startswith("meta-inf/"):
        return "Signing / Metadata"
    if lower_name.startswith("assets/"):
        return "Raw Assets"
    return "Other"


def detect_architectures(files):
    archs = set()
    for f in files:
        m = re.match(r'lib/([^/]+)/', f)
        if m:
            archs.add(m.group(1))
    return archs


def detect_locales(files):
    locales = set()
    for f in files:
        m = re.search(r'values-([a-zA-Z]{2}(?:-r[A-Z]{2})?)/', f)
        if m:
            locales.add(m.group(1))
    return locales


def detect_signing_info(files):
    info = set()
    for f in files:
        low = f.lower()
        if low.startswith("meta-inf/") and low.endswith((".rsa", ".dsa", ".ec")):
            info.add(f"Certificate file: {f}")
        if low.endswith("stamp-cert-sha256"):
            info.add("Play Store signing stamp present (v3+ hints)")
    return info


def detect_split_bundles(files):
    splits = set()
    for f in files:
        m = re.search(r'(config\.[a-zA-Z0-9_]+|split_[a-zA-Z0-9_]+)\.apk', f)
        if m:
            splits.add(m.group(1))
    return splits


def detect_third_party_sdks(class_paths, config_strings):
    found = set()
    haystacks = [t.lower() for t in class_paths] + [t.lower() for t in list(config_strings)[:3000]]
    for sdk_name, sigs in SDK_SIGNATURES.items():
        for sig in sigs:
            sig_l = sig.lower()
            if any(sig_l in h for h in haystacks):
                found.add(sdk_name)
                break
    return found


def scan_for_secrets(token_sets):
    findings = set()
    pool = []
    for s in token_sets:
        pool.extend(list(s)[:4000])
    for pattern_name, pattern in SECRET_PATTERNS.items():
        for tok in pool:
            m = re.search(pattern, tok)
            if m:
                findings.add(f"{pattern_name} → {m.group(0)[:44]}")
                break
        if len(findings) > 25:
            break
    return findings


def process_zip_archive(zip_obj, details):
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

        lower_name = name.lower()
        category = categorize_file(lower_name)
        details["category_sizes"][category] = details["category_sizes"].get(category, 0) + info.file_size

        if name.endswith('/') or info.file_size == 0:
            continue

        if any(lower_name.endswith(ext) for ext in ['.png', '.webp', '.jpg']) and info.file_size < 300 * 1024:
            if not any(ignore in lower_name for ignore in ["icon", "launcher", "splash"]):
                try:
                    details["images"][name.split('/')[-1]] = zip_obj.read(name)
                except Exception:
                    pass

        try:
            raw_bytes = zip_obj.read(name) if info.file_size < 10 * 1024 * 1024 else zip_obj.open(name).read(5 * 1024 * 1024)

            if any(lower_name.endswith(ext) for ext in [".db", ".sqlite"]):
                details["db_schemas"].update(inspect_sqlite_db(raw_bytes))

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
                for cm in class_matches[:150]:
                    decoded_cls = cm.decode('ascii', errors='ignore')
                    if not is_framework_noise(decoded_cls):
                        details["class_paths"].add(decoded_cls)

                anno_matches = re.findall(rb'(?:SerializedName|Keep|Beta|Experimental|RequiresOptIn)[A-Za-z0-9_"\':\s]{2,60}', raw_bytes)
                for am in anno_matches:
                    try:
                        details["annotations"].add(am.decode('ascii', errors='ignore').strip())
                    except Exception:
                        pass

            details["xor_urls"].update(check_xor_obfuscation(raw_bytes))
            file_tokens = extract_strings_from_bytes(raw_bytes)

            if lower_name.endswith(".so"):
                for token in file_tokens:
                    if token.startswith("_Z"):
                        details["native_strings"].add(demangle_cpp_symbol(token))
                    else:
                        details["native_strings"].add(token)
            elif any(lower_name.endswith(ext) for ext in [".csv", ".json", ".proto", ".txt", ".dat", ".xml", ".properties"]):
                details["config_strings"].update(file_tokens)
            else:
                details["all_strings"].update(file_tokens)

            # resources.arsc holds the compiled global string pool — this is
            # the real equivalent of "strings.xml" inside a packaged APK,
            # since plain-text res/values/*.xml files don't survive the
            # build. We re-scan its tokens and keep only the ones that look
            # like human-facing copy rather than paths/class descriptors.
            if lower_name.endswith("resources.arsc") or lower_name.endswith(".arsc"):
                details["ui_strings"].update(t for t in file_tokens if looks_like_ui_text(t))

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
    details = {
        "files": set(), "total_size": 0,
        "all_strings": set(), "native_strings": set(), "config_strings": set(),
        "annotations": set(), "protobuf_schemas": set(), "graphql_ops": set(),
        "jni_exports": set(), "class_paths": set(), "db_schemas": set(),
        "xor_urls": set(), "activities": set(), "services": set(),
        "permissions": set(), "deep_links": set(), "endpoints": set(),
        "images": {}, "category_sizes": {}, "ui_strings": set(),
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

    st.markdown('<div class="section-label">📊 Quick Facts (no AI — instant)</div>', unsafe_allow_html=True)

    tiles = f"""
    <div class="tile-grid">
        <div class="tile"><div class="tile-val">{'+' if size_diff >= 0 else ''}{size_diff} MB</div><div class="tile-lbl">SIZE CHANGE ({old_size_mb}→{new_size_mb} MB)</div></div>
        <div class="tile"><div class="tile-val">{len(new_data['files']) - len(old_data['files']):+d}</div><div class="tile-lbl">NET FILE COUNT CHANGE</div></div>
        <div class="tile"><div class="tile-val">{len(new_sdks)}</div><div class="tile-lbl">NEW 3RD-PARTY SDKs</div></div>
        <div class="tile"><div class="tile-val">{len(new_data['jni_exports'] - old_data['jni_exports'])}</div><div class="tile-lbl">NEW JNI NATIVE EXPORTS</div></div>
    </div>
    """
    st.markdown(tiles, unsafe_allow_html=True)

    chips = '<div class="chip-row">'
    for a in sorted(new_archs):
        chips += f'<span class="chip">🏗️ new arch: {a}</span>'
    for l in sorted(new_locales)[:8]:
        chips += f'<span class="chip">🌐 new locale: {l}</span>'
    for s in sorted(new_splits):
        chips += f'<span class="chip">📦 split: {s}</span>'
    if not new_archs and not new_locales and not new_splits:
        chips += '<span class="chip">no new architectures / locales / splits</span>'
    chips += '</div>'
    st.markdown(chips, unsafe_allow_html=True)

    if secrets_new:
        st.markdown('<div class="chip-row"><span class="chip chip-warn">⚠️ possible exposed secrets found in NEW build</span></div>', unsafe_allow_html=True)
        with st.expander(f"🔐 Potential exposed secrets ({len(secrets_new)}) — verify manually"):
            for s in sorted(secrets_new):
                st.markdown(f'<div class="mono-block">{s}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="chip-row"><span class="chip chip-ok">✅ no obvious hardcoded secrets pattern-matched</span></div>', unsafe_allow_html=True)

    with st.expander("🧩 Third-party SDK ecosystem"):
        if new_sdks:
            st.markdown("**Newly added:**")
            st.markdown('<div class="chip-row">' + "".join(f'<span class="chip chip-ok">{s}</span>' for s in sorted(new_sdks)) + '</div>', unsafe_allow_html=True)
        if removed_sdks:
            st.markdown("**Removed:**")
            st.markdown('<div class="chip-row">' + "".join(f'<span class="chip chip-warn">{s}</span>' for s in sorted(removed_sdks)) + '</div>', unsafe_allow_html=True)
        st.markdown("**All SDKs detected in new build:**")
        st.markdown('<div class="chip-row">' + "".join(f'<span class="chip">{s}</span>' for s in sorted(new_data["third_party_sdks"])) + '</div>', unsafe_allow_html=True)

    with st.expander("📦 Size breakdown by category (new build)"):
        cats = sorted(new_data["category_sizes"].items(), key=lambda x: -x[1])
        for cat, size in cats:
            mb = round(size / (1024 * 1024), 2)
            if mb > 0.01:
                st.markdown(f"**{cat}** — {mb} MB")

    with st.expander("🔏 Signing & packaging metadata"):
        sign_new = new_data["signing_info"]
        if sign_new:
            for s in sorted(sign_new):
                st.markdown(f"- {s}")
        else:
            st.markdown("_No META-INF signature files found in this archive (may be unsigned bundle or AAB)._")
        if new_data["architectures"]:
            st.markdown(f"**Architectures shipped:** {', '.join(sorted(new_data['architectures']))}")
        if new_data["locales"]:
            st.markdown(f"**Locales included:** {len(new_data['locales'])} ({', '.join(sorted(new_data['locales'])[:15])}{'…' if len(new_data['locales']) > 15 else ''})")

    added_ui = sorted(new_data["ui_strings"] - old_data["ui_strings"])
    removed_ui = sorted(old_data["ui_strings"] - new_data["ui_strings"])
    with st.expander(f"🔤 New UI-facing text / labels ({len(added_ui)})"):
        st.caption("Pulled from resources.arsc's compiled string pool — the real equivalent of strings.xml inside a built APK, filtered to human-readable copy.")
        if added_ui:
            for s in added_ui[:250]:
                st.markdown(f"- {s}")
            if len(added_ui) > 250:
                st.caption(f"…and {len(added_ui) - 250} more (truncated for display).")
        else:
            st.markdown("_No new UI copy detected between builds._")
        if removed_ui:
            st.markdown(f"**Removed ({len(removed_ui)}):**")
            for s in removed_ui[:100]:
                st.markdown(f"- ~~{s}~~")
            if len(removed_ui) > 100:
                st.caption(f"…and {len(removed_ui) - 100} more (truncated for display).")

    with st.expander("🧾 Raw string diff — unfiltered (no AI, everything found)"):
        st.caption("Every added/removed printable string across code, config, and native files. Use this to verify AI claims yourself.")
        raw_added = sorted((new_data["all_strings"] | new_data["config_strings"]) - (old_data["all_strings"] | old_data["config_strings"]))
        raw_removed = sorted((old_data["all_strings"] | old_data["config_strings"]) - (new_data["all_strings"] | new_data["config_strings"]))
        tab_add, tab_rem = st.tabs([f"➕ Added ({len(raw_added)})", f"➖ Removed ({len(raw_removed)})"])
        with tab_add:
            for s in raw_added[:400]:
                st.markdown(f'<div class="mono-block">{s}</div>', unsafe_allow_html=True)
            if len(raw_added) > 400:
                st.caption(f"…and {len(raw_added) - 400} more (truncated for display).")
        with tab_rem:
            for s in raw_removed[:400]:
                st.markdown(f'<div class="mono-block">{s}</div>', unsafe_allow_html=True)
            if len(raw_removed) > 400:
                st.caption(f"…and {len(raw_removed) - 400} more (truncated for display).")


# ==================== FULLSCREEN REPORT VIEW ====================
if st.session_state.report_html:
    if st.session_state.added_image_keys:
        with st.expander("🖼️ Newly Added Graphic Previews", expanded=False):
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

    st.markdown('<div class="section-label">🤖 AI Teardown Report</div>', unsafe_allow_html=True)
    st.markdown(st.session_state.report_html, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Start New Scan", use_container_width=True):
        st.session_state.report_html = None
        st.session_state.added_image_keys = []
        st.session_state.new_data_images = {}
        st.session_state.quickfacts = None
        st.rerun()

# ==================== MAIN INPUT VIEW ====================
else:
    st.markdown("""
    <div class="hero-card">
        <div class="hero-title-row">
            <div class="icon-badge">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="5" y="2" width="14" height="20" rx="3" ry="3"></rect>
                    <line x1="12" y1="18" x2="12.01" y2="18"></line>
                    <path d="M9 6h6"></path>
                </svg>
            </div>
            <div class="hero-title">APK Teardown Studio</div>
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

    old_file = st.file_uploader("Old Version (.apk, .aab, .xapk, .apks)", type=["apk", "aab", "xapk", "apks", "zip"])
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
                <div class="radar-ring"></div>
                <div style="font-weight: 700; font-size: 15px; color: #D0BCFF;">Decompressing Archives & Native JNI Bridges</div>
                <div style="font-size: 12px; color: #CAC4D0; margin-top: 4px;">Demangling C++ symbols, mapping GraphQL & ProtoBufs...</div>
            </div>
            """, unsafe_allow_html=True)

            old_bytes = old_file.read()
            new_bytes = new_file.read()

            old_data = inspect_entire_bundle(old_bytes)
            new_data = inspect_entire_bundle(new_bytes)
            st.session_state.quickfacts = (old_data, new_data)

            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="radar-ring"></div>
                <div style="font-weight: 700; font-size: 15px; color: #D0BCFF;">Diffing Bytecode, SDKs & Signing Metadata</div>
                <div style="font-size: 12px; color: #CAC4D0; margin-top: 4px;">Scanning for exposed secrets, ABI splits, locale diffs...</div>
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

            === 8. THIRD-PARTY SDK ECOSYSTEM ===
            NEW SDKs: {added_sdks}
            REMOVED SDKs: {removed_sdks}

            === 9. PACKAGING / ARCHITECTURE / LOCALIZATION ===
            NEW NATIVE ARCHITECTURES: {added_archs}
            NEW LOCALES: {added_locales}
            SIGNING INFO (new build): {list(new_data['signing_info'])}
            SPLIT BUNDLES (new build): {list(new_data['splits'])}

            === 10. POTENTIAL EXPOSED SECRETS (pattern-matched only, verify manually) ===
            {secrets_found[:20]}

            === 11. NEW UI-FACING TEXT / LABELS (from resources.arsc string pool) ===
            {added_ui_strings[:40]}
            """

            scanner_placeholder.markdown("""
            <div class="scanner-box">
                <div class="radar-ring"></div>
                <div style="font-weight: 700; font-size: 15px; color: #D0BCFF;">Synthesizing AI Teardown Dashboard</div>
                <div style="font-size: 12px; color: #CAC4D0; margin-top: 4px;">Formulating unreleased predictions & technical audits...</div>
            </div>
            """, unsafe_allow_html=True)

            client = Groq(api_key=st.secrets["GROQ_API_KEY"])

            prompt = f"""
            You are a lead mobile teardown investigator. Examine these package diffs and output a clean, modern Material Design 3 dashboard report in HTML.
            Output strictly raw, valid HTML with inline CSS. Do NOT wrap output in markdown codeblocks (do NOT use ```html or ```).
            Be thorough and specific — write substantive analysis paragraphs (not just bullet fragments), referencing concrete class/file/endpoint names from the data. Where evidence is thin, say so explicitly rather than inventing detail.

            Design specifications:
            - **Top Metric Chips Row**: `display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px;`. Pills: `background: #EADDFF; color: #21005D; padding: 4px 10px; border-radius: 100px; font-size: 11px; font-weight: bold;`. Include Size Change ({size_diff_mb} MB), Impact Rating (e.g. 8/10), New Flags ({len(feature_toggles)}), New JNI Bridges ({len(added_jni)}), New SDKs ({len(added_sdks)}).

            - **Card 1 (AI Analysis & Executive Summary)**: `background-color: #F3EDF7; border-radius: 16px; padding: 14px; margin-bottom: 12px; border-left: 4px solid #6750A4;`. Header with SVG sparkle icon + `<span style="font-weight:700;font-size:15px;color:#1D1B20;">AI Analysis & Executive Summary</span>`. 3-5 sentences of plain-language narrative on what actually changed and why it matters.

            - **Card 2 (Unreleased Feature Blueprints)**: `background-color: #FFD8E4; color: #31111D; border-radius: 16px; padding: 14px; margin-bottom: 12px; border-left: 4px solid #B12B58;`. Header with SVG lightning icon + title. Concrete predictions about unreleased features, each backed by cited flag/class/endpoint names — prioritize citing actual human-readable strings from section 11 (NEW UI-FACING TEXT) when available, since those are the strongest signal of what a feature is actually called and does. Include copyable terminal blocks (`background-color:#1D1B20;color:#E6E1E5;padding:8px 12px;border-radius:8px;font-family:monospace;font-size:11px;word-break:break-all;margin-top:6px;`) showing example adb/grep commands to inspect the evidence.

            - **Card 3 (Exact Package Technical Diffs)**: `background-color: #F7F2FA; border-radius: 16px; padding: 14px; margin-bottom: 12px; border: 1px solid #CAC4D0; border-left: 4px solid #79747E;`. Header with SVG code icon + title. Bullet list of new JNI methods, ProtoBuf schemas, GraphQL queries, endpoints, screens, services, permissions.

            - **Card 4 (Security, SDKs & Packaging Risk)**: `background-color: #FFF3E0; color: #3E2723; border-radius: 16px; padding: 14px; margin-bottom: 12px; border-left: 4px solid #E8A33D;`. Header with SVG shield icon + `<span style="font-weight:700;font-size:15px;color:#3E2723;">Security, SDKs & Packaging Risk</span>`. Cover: newly added/removed third-party SDKs and what data they typically collect, any pattern-matched secrets (flag clearly as "needs manual verification, may be a false positive"), new native architectures / locales / split bundles, and signing metadata observations. If secrets list is empty, state that plainly as a positive finding.

            RAW CATEGORIZED PACKAGE DIFF DATA:
            {diff_summary}
            """

            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=8000,
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
