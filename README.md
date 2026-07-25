# APK Teardown Studio

A web-based, mobile-friendly analysis tool that lets you compare two versions of an Android app and see exactly what changed under the hood. Whether you are looking for unreleased features, new API endpoints, or architectural updates, APK Teardown Studio breaks down complex binary differences into a clean, easy-to-read dashboard directly from your phone browser.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Ready-red)
![Groq](https://img.shields.io/badge/AI-Groq-orange)

---

## Key Features

* **Deep Package Diffing:** Upload two versions of an app (`.apk`, `.aab`, `.xapk`, `.apks`, or `.zip`) to instantly see what files, images, and resources were added or removed.
* **Code & Architecture Insights:** Maps out new Native C++ JNI bridges, GraphQL queries, ProtoBuf schemas, SQLite database tables, and DEX class changes.
* **SDK & Security Ecosystem:** Tracks newly added or removed third-party SDKs and sweeps for potential exposed secrets (like API keys or tokens).
* **UI-Facing Text Extraction:** Pulls readable text straight from the compiled `resources.arsc` pool to show you exactly what new labels or promotional copy are being added to the app.
* **AI-Powered Summaries:** Uses the Groq AI engine to synthesize raw technical diffs into a plain-language executive summary, complete with predicted feature blueprints and helpful `adb` terminal commands.
* **One-Click JADX Decompilation:** Extract and download the decompiled Java source code as a `.zip` file directly from the interface.

---

## Requirements

To run this application, you only need three Python libraries:
* `streamlit`
* `groq`
* `Pillow`

You will also need a **Groq API Key** to power the AI teardown reports. You can get one for free from the Groq Console.

---

## Setup & Installation

### Option 1: Running on Streamlit Community Cloud (Recommended)
This app is designed to run smoothly on Streamlit Cloud, making it fully accessible and fast from a mobile browser without needing to install any heavy desktop programs.
1. Fork or upload this repository to your GitHub account.
2. Log into Streamlit Community Cloud and create a new app pointing to your repository.
3. Before deploying, go to **Advanced Settings** and add your Groq API key to the Secrets:
   ```toml
   GROQ_API_KEY = "your-api-key-here"
   ```
4. Click Deploy.

### Option 2: Running Locally
1. Clone this repository to your machine.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.streamlit` folder in the root directory, and inside it, create a `secrets.toml` file with your API key:
   ```toml
   GROQ_API_KEY = "your-api-key-here"
   ```
4. Start the app:
   ```bash
   streamlit run app.py
   ```

---

## How to Use

1. Upload the older version of the app in the first slot.
2. Upload the newer version of the app in the second slot.
3. Tap **Run Deep Package Teardown**.
4. The app will immediately decompress the archives, demangle C++ symbols, map out the SDKs, and generate a clean dashboard showing the exact changes.
5. Expand the dropdowns to explore raw strings and UI copy, or trigger the JADX Decompiler at the bottom to download the raw Java source.

---

## Notes

* **File Limits:** Streamlit typically limits file uploads to 200MB by default. If you are handling massive files, you may need to adjust your Streamlit config file to allow larger uploads.
* **JADX Execution:** The app downloads a lightweight, standalone JADX binary on the fly to decompile the code.


> Built for tech enthusiasts, journalists, and developers looking to keep an eye on app updates.
