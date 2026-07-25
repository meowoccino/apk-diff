import streamlit as st
import zipfile
import io
import re
from groq import Groq
from androguard.core.bytecodes.axml import AXMLPrinter
from androguard.core.bytecodes.arsc import ARSCParser
import xml.etree.ElementTree as ET

# Page Setup & Styling
st.set_page_config(page_title="APK Teardown Studio", page_icon="📱", layout="centered")

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

st.markdown('<div class="title-text">📱 APK & Bundle Teardown Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Journalist-grade scanner: Decodes binary Manifests, resource tables, and layout additions.</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    old_file = st.file_uploader("Old Version (.apk / .aab)", type=["apk", "aab"])
with col2:
    new_file = st.file_uploader("New Version (.apk / .aab)", type=["apk", "aab"])

def extract_manifest_components(zip_obj):
    """Decodes binary AndroidManifest.xml into readable XML elements (activities, permissions, meta-data)."""
    components = {"activities": set(), "permissions": set(), "meta_data": set(), "services": set()}
    manifest_paths = [f for f in zip_obj.namelist() if f.endswith("AndroidManifest.xml")]
    
    for path in manifest_paths:
        try:
            raw_axml = zip_obj.read(path)
            axml = AXMLPrinter(raw_axml)
            xml_tree = ET.fromstring(axml.get_buff())
            
            for elem in xml_tree.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                name = elem.attrib.get('{http://schemas.android.com/apk/res/android}name') or elem.attrib.get('name')
                value = elem.attrib.get('{http://schemas.android.com/apk/res/android}value') or elem.attrib.get('value')
                
                if name:
                    if tag == "activity" or tag == "activity-alias":
                        components["activities"].add(name)
                    elif tag == "uses-permission" or tag == "permission":
                        components["permissions"].add(name)
                    elif tag == "service" or tag == "receiver":
                        components["services"].add(name)
                    elif tag == "meta-data":
                        components["meta_data"].add(f"{name} = {value}" if value else name)
        except Exception:
            pass
    return components

def extract_resource_strings(zip_obj):
    """Decodes binary resources.arsc table to extract clean user-facing strings."""
    strings = set()
    arsc_paths = [f for f in zip_obj.namelist() if f.endswith("resources.arsc")]
    
    for path in arsc_paths:
        try:
            raw_arsc = zip_obj.read(path)
            arsc = ARSCParser(raw_arsc)
            for pkg in arsc.get_packages_names():
                for s in arsc.get_strings_resources():
                    cleaned = s.strip()
                    if len(cleaned) > 3 and not cleaned.startswith("res/"):
                        strings.add(cleaned)
        except Exception:
            pass
    return strings

def inspect_bundle(file_bytes):
    """Performs deep teardown decoding on an uploaded package."""
    details = {"files": set(), "total_size": 0, "layouts": set()}
    with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
        for name in z.namelist():
            info = z.getinfo(name)
            details["files"].add(name)
            details["total_size"] += info.file_size
            if "layout" in name and name.endswith(".xml"):
                details["layouts"].add(name.split('/')[-1])
        
        components = extract_manifest_components(z)
        strings = extract_resource_strings(z)
        
    return details, components, strings

if st.button("🚀 Analyze & Run Teardown", type="primary", use_container_width=True):
    if "GROQ_API_KEY" not in st.secrets or not st.secrets["GROQ_API_KEY"]:
        st.error("GROQ_API_KEY is missing from Streamlit Secrets!")
    elif not old_file or not new_file:
        st.error("Please upload both Old and New package files.")
    else:
        with st.spinner("Decoding binary XMLs, parsing string tables, and querying Groq..."):
            old_bytes = old_file.read()
            new_bytes = new_file.read()
            
            old_details, old_comp, old_strings = inspect_bundle(old_bytes)
            new_details, new_comp, new_strings = inspect_bundle(new_bytes)
            
            # Precise Diffs
            added_activities = list(new_comp["activities"] - old_comp["activities"])
            added_permissions = list(new_comp["permissions"] - old_comp["permissions"])
            added_meta = list(new_comp["meta_data"] - old_comp["meta_data"])
            added_strings = list(new_strings - old_strings)
            added_layouts = list(new_details["layouts"] - old_details["layouts"])
            
            old_size_mb = round(old_details["total_size"] / (1024 * 1024), 2)
            new_size_mb = round(new_details["total_size"] / (1024 * 1024), 2)
            size_diff_mb = round(new_size_mb - old_size_mb, 2)
            
            diff_summary = f"""
            OLD FILE: {old_file.name} ({old_size_mb} MB)
            NEW FILE: {new_file.name} ({new_size_mb} MB) | SIZE DIFF: {size_diff_mb} MB
            
            NEWLY ADDED MANIFEST ACTIVITIES / SCREENS ({len(added_activities)}):
            {added_activities[:30]}
            
            NEWLY ADDED META-DATA / FEATURE FLAGS ({len(added_meta)}):
            {added_meta[:30]}
            
            NEWLY ADDED PERMISSIONS ({len(added_permissions)}):
            {added_permissions[:20]}
            
            NEWLY ADDED UI LAYOUT FILES ({len(added_layouts)}):
            {added_layouts[:30]}
            
            NEW STRINGS FROM RESOURCES ({len(added_strings)} total, showing top 50):
            {added_strings[:50]}
            """
            
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            
            prompt = f"""
            You are an investigative tech reporter conducting a professional APK Teardown (like 9to5Google or Android Authority).
            Examine these decoded Manifest and String diffs to reveal what unreleased features, redesigns, or hidden updates the developers are preparing.
            
            Output strictly raw, clean HTML with inline CSS styled cleanly with Material Design 3 (MD3) guidelines.
            Do NOT wrap your output in markdown codeblocks (do NOT use ```html or ```).
            
            Styling guidelines:
            - Standard Cards: background-color: #F7F2FA; border-radius: 18px; padding: 16px; margin-bottom: 16px; border: 1px solid #CAC4D0;
            - Unreleased Spotlight Card: background-color: #FFD8E4; color: #31111D; border-radius: 20px; padding: 16px; margin-bottom: 16px;
            - AI Overview Card: background-color: #EADDFF; color: #21005D; border-radius: 18px; padding: 16px; margin-bottom: 16px;
            - Terminal / Command Blocks: background-color: #1D1B20; color: #E6E1E5; padding: 8px 12px; border-radius: 8px; font-family: monospace; font-size: 11px; word-break: break-all; margin-top: 6px;
            - Stat Badges: background-color: #CCE8E1; color: #05211B; font-weight: bold; padding: 4px 10px; border-radius: 100px; font-size: 11px; display: inline-block; margin-right: 4px;

            Your report MUST include:
            1. **Diff Stat Badges**: Showing size change, new activities count, new strings count, and layout additions.
            2. **Executive Teardown Verdict**: A clear summary explaining what features are in active development.
            3. **Unreleased Clues & Activation Commands**: Connect new strings, hidden activities, and meta-data flags into cohesive feature predictions. Provide realistic copyable shell commands (`adb shell device_config put...` or `adb shell am start...`).
            4. **Detailed Additions Breakdown**: Grouped sections for New Screens/Activities, New User Strings, and New Permissions.

            RAW DECODED DIFF DATA:
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
