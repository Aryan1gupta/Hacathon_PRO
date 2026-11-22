"""YojanaMitra AI - Phase 1 Streamlit dashboard (profile form + scheme list)."""
import json
import os
from datetime import date

import streamlit as st
 
# Eligibility engine: checks each scheme against the saved profile.
from engine.eligibility import check_all, STATUS_POTENTIAL, STATUS_NOT_MATCHED, STATUS_NEEDS_VERIFICATION
from engine.eligibility import missing_fields
from engine.checklist import build_checklist
# Natural-language extraction: pulls state, education and income out of free text.
from engine.nlp_extract import extract_profile_from_text
# Personalised document checklist for each scheme.
from engine.checklist import build_checklists
# SQLite application tracker and deadline reminders.
from engine.tracker import (
    init_db, set_status, list_statuses, deadline_reminders,
    STATUS_DISCOVERED, STATUS_DOCS_PENDING, STATUS_SUBMITTED, STATUS_USER_REPORTED,
)

# Page settings must be the first Streamlit call in the script.
st.set_page_config(page_title="YojanaMitra AI", page_icon="🎓", layout="wide")
st.markdown(
    """
    <style>
    :root { --ym-bg:#0B1220; --ym-side:#0F1A2C; --ym-card:#142238; --ym-green:#10B981;
            --ym-accent:#34D399; --ym-text:#F1F5F9; --ym-muted:#94A3B8; --ym-border:#1F2F47; }
    .stApp { background-color: var(--ym-bg); color: var(--ym-text); }
    section[data-testid="stSidebar"] { background-color: var(--ym-side); border-right: 1px solid var(--ym-border); }
    h1, h2, h3 { color: var(--ym-text) !important; letter-spacing: -0.01em; }
    p, li, label, small { color: var(--ym-muted); }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: var(--ym-card); border: 1px solid var(--ym-border) !important;
        border-radius: 14px; box-shadow: 0 1px 2px rgba(0,0,0,.35); transition: border-color .2s ease; }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color: var(--ym-green) !important; }
    .stButton > button { border-radius: 10px; border: 1px solid var(--ym-border); background: var(--ym-card);
        color: var(--ym-text); transition: all .2s ease; }
    .stButton > button:hover { border-color: var(--ym-accent); color: var(--ym-accent); }
    .stButton > button[kind="primary"] { background: var(--ym-green); border-color: var(--ym-green); color: #04110A; font-weight: 600; }
    .ym-stat-value { color: var(--ym-accent); font-size: 30px; font-weight: 700; line-height: 1.1; }
    .ym-stat-label { color: var(--ym-muted); font-size: 13px; }
    .ym-pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px;
        border:1px solid var(--ym-green); color: var(--ym-accent); }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow: 0 4px 14px rgba(0,0,0,.4); }
    .stButton > button:focus:not(:active) { box-shadow: 0 0 0 2px rgba(52,211,153,.35); }
    .ym-brand { color: var(--ym-text); font-weight: 700; font-size: 20px; padding-top: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# All UI text lives here. "en" = English, "hi" = Hindi.
TEXTS = {
    "en": {
        "tagline": "Find and understand scholarship schemes for students.",
        "nav": "Navigation",
        "page_home": "Home",
        "page_profile": "Student Profile",
        "page_schemes": "Schemes",
        "home_title": "Welcome to YojanaMitra AI",
        "home_intro": (
            "YojanaMitra AI helps students learn about government scholarship schemes. "
            "Save your basic student profile, then browse the available schemes in "
            "English or Hindi. This version only displays information; it does not "
            "check eligibility yet."
        ),
        "card_profile": "Profile status",
        "card_profile_saved": "Saved",
        "card_profile_missing": "Not saved yet",
        "card_schemes": "Schemes available",
        "card_language": "Language",
        "lang_name": "English",
        "profile_title": "Student Profile",
        "profile_intro": "Fill in your details and save them.",
        "state": "State / Union Territory",
        "education": "Education Level",
        "course": "Course",
        "year": "Academic Year",
        "income": "Family Annual Income (INR)",
        "save": "Save Profile",
        "saved_ok": "Profile saved successfully!",
        "saved_summary": "Saved profile",
        "no_profile": "No profile saved yet.",
        "schemes_title": "Scholarship Schemes",
        "schemes_intro": "Click a scheme to see its details.",
        "ministry": "Ministry",
        "link": "Official website",
        "no_schemes": "No schemes found. Check data/schemes.json.",
        "status_potential": "Potential match",
        "status_not_matched": "Not matched",
        "status_needs_verification": "Needs verification",
        "edu_options": ["Class 10", "Class 12", "Undergraduate", "Postgraduate", "Other"],
        "year_options": ["1st Year", "2nd Year", "3rd Year", "4th Year", "Completed"],
        "nl_title": "Describe yourself in your own words",
        "nl_intro": (
            "Write about your state, education and family income in English or Hindi. "
            "The app only uses what it finds; anything missing stays empty for you to fill in."
        ),
        "nl_placeholder": (
            "Example: I am from Bihar, I passed Class 12, family income is 2 lakh per year.\n"
            "उदाहरण: मैं बिहार से हूँ, मैंने कक्षा 12 पास किया है, परिवार की सालाना आय 2 लाख है।"
        ),
        "nl_button": "Extract information",
        "nl_confirm_title": "Please confirm the details extracted from your text",
        "nl_not_found": "— Not found —",
        "not_selected": "— Not selected —",
        "nl_confirm_button": "Confirm and use these details",
        "nl_saved": "Details confirmed and saved to your profile.",
        "nl_income_found": "Income found in text",
        "nl_found_hint": (
            "Values not found in your text are left empty. Check and correct them before confirming."
        ),
        "page_tracker": "Tracker",
        "tr_title": "Application Tracker",
        "tr_intro": "Check deadlines and required documents, and track your applications.",
        "tr_no_deadlines": "No upcoming deadlines found in the verified scheme data.",
        "tr_deadline_line": "{scheme_id}: deadline {deadline} ({days_left} days left)",
        "tr_checklist_title": "Document checklist",
        "tr_no_checklist": "No document checklist yet. Save your profile first.",
        "tr_status_title": "Application status",
        "tr_saved": "Status saved.",
        "tr_save_button": "Save",
        "tr_status_discovered": "Discovered",
        "tr_status_docs_pending": "Documents pending",
        "tr_status_submitted": "Submitted",
        "tr_status_user_reported": "Reported by me (applied outside app)",
        "cat_potential": "Potentially Eligible",
        "cat_needs": "Needs More Information",
        "cat_not": "Not Eligible",
        "cat_none": "No schemes in this group.",
        "missing_info": "Missing information",
        "checklist_title": "Document checklist",
        "link_unverified": "Official link not verified yet. Please search for this scheme on the official portal.",
        "needs_explain": "Your details match the state, education and income rules. The schemes below still need a document check, because the app cannot verify caste, minority, dependant or marks conditions from your profile.",
        "header_band": "YojanaMitra AI · Scholarship guidance for students",
        "signin_title": "Sign in (demo)",
        "signin_help": "Demo only: enter a display name. No password or ID number is needed or stored. Your name is kept only for this browser session.",
        "signin_name": "Display name",
        "signin_button": "Sign in",
        "signin_guest": "Continue as guest",
        "signed_in_as": "Signed in as",
        "signout": "Sign out",
        "footer_text": "Sample scheme information for learning only. Always confirm eligibility, documents and deadlines on the official government portal.",
        "footer_built": "YojanaMitra AI · Python + Streamlit · No external AI services",
        "home_greeting": "Hello",
    },
    "hi": {
        "tagline": "छात्रों के लिए छात्रवृत्ति योजनाओं को खोजें और समझें।",
        "nav": "नेविगेशन",
        "page_home": "होम",
        "page_profile": "छात्र प्रोफ़ाइल",
        "page_schemes": "योजनाएँ",
        "home_title": "योजनामित्र AI में आपका स्वागत है",
        "home_intro": (
            "योजनामित्र AI छात्रों को सरकारी छात्रवृत्ति योजनाओं की जानकारी देता है। "
            "अपनी बुनियादी छात्र प्रोफ़ाइल सहेजें, फिर उपलब्ध योजनाएँ हिंदी या अंग्रेज़ी में देखें। "
            "इस संस्करण में केवल जानकारी दिखाई जाती है; पात्रता की जाँच अभी नहीं होती।"
        ),
        "card_profile": "प्रोफ़ाइल स्थिति",
        "card_profile_saved": "सहेजा गया",
        "card_profile_missing": "अभी सहेजा नहीं गया",
        "card_schemes": "उपलब्ध योजनाएँ",
        "card_language": "भाषा",
        "lang_name": "हिंदी",
        "profile_title": "छात्र प्रोफ़ाइल",
        "profile_intro": "अपनी जानकारी भरें और सहेजें।",
        "state": "राज्य / केंद्र शासित प्रदेश",
        "education": "शिक्षा स्तर",
        "course": "पाठ्यक्रम",
        "year": "शैक्षणिक वर्ष",
        "income": "पारिवारिक वार्षिक आय (INR)",
        "save": "प्रोफ़ाइल सहेजें",
        "saved_ok": "प्रोफ़ाइल सफलतापूर्वक सहेजी गई!",
        "saved_summary": "सहेजी गई प्रोफ़ाइल",
        "no_profile": "अभी कोई प्रोफ़ाइल सहेजी नहीं गई है।",
        "schemes_title": "छात्रवृत्ति योजनाएँ",
        "schemes_intro": "विवरण देखने के लिए किसी योजना पर क्लिक करें।",
        "ministry": "मंत्रालय",
        "link": "आधिकारिक वेबसाइट",
        "no_schemes": "कोई योजना नहीं मिली। data/schemes.json जाँचें।",
        "status_potential": "संभावित पात्रता",
        "status_not_matched": "पात्र नहीं",
        "status_needs_verification": "सत्यापन आवश्यक",
        "edu_options": ["कक्षा 10", "कक्षा 12", "स्नातक", "स्नातकोत्तर", "अन्य"],
        "year_options": ["प्रथम वर्ष", "द्वितीय वर्ष", "तृतीय वर्ष", "चतुर्थ वर्ष", "पूर्ण"],
        "nl_title": "अपने शब्दों में अपना परिचय दें",
        "nl_intro": (
            "अपने राज्य, शिक्षा और पारिवारिक आय के बारे में हिंदी या अंग्रेज़ी में लिखें। "
            "ऐप केवल वही लेता है जो उसे मिलता है; बाकी जानकारी आप खुद भरेंगे।"
        ),
        "nl_placeholder": (
            "उदाहरण: मैं बिहार से हूँ, मैंने कक्षा 12 पास किया है, परिवार की सालाना आय 2 लाख है।\n"
            "Example: I am from Bihar, I passed Class 12, family income is 2 lakh per year."
        ),
        "nl_button": "जानकारी निकालें",
        "nl_confirm_title": "आपके लिखे पाठ से निकाली गई जानकारी की पुष्टि करें",
        "nl_not_found": "नहीं मिला",
        "not_selected": "— चुना नहीं गया —",
        "nl_confirm_button": "पुष्टि करें और ये विवरण उपयोग करें",
        "nl_saved": "विवरण की पुष्टि हो गई और प्रोफ़ाइल में सहेज दिए गए।",
        "nl_income_found": "पाठ में आय मिली",
        "nl_found_hint": (
            "आपके पाठ में न मिली जानकारी खाली रखी गई है। पुष्टि से पहले उसे जाँचें और सुधारें।"
        ),
        "page_tracker": "ट्रैकर",
        "tr_title": "आवेदन ट्रैकर",
        "tr_intro": "अंतिम तिथियाँ और आवश्यक दस्तावेज़ देखें, और अपने आवेदनों की स्थिति ट्रैक करें।",
        "tr_no_deadlines": "सत्यापित योजना डेटा में कोई आगामी अंतिम तिथि नहीं मिली।",
        "tr_deadline_line": "{scheme_id}: अंतिम तिथि {deadline} ({days_left} दिन शेष)",
        "tr_checklist_title": "दस्तावेज़ सूची",
        "tr_no_checklist": "अभी कोई दस्तावेज़ सूची नहीं है। पहले अपनी प्रोफ़ाइल सहेजें।",
        "tr_status_title": "आवेदन की स्थिति",
        "tr_saved": "स्थिति सहेजी गई।",
        "tr_save_button": "सहेजें",
        "tr_status_discovered": "खोजा गया",
        "tr_status_docs_pending": "दस्तावेज़ बाकी",
        "tr_status_submitted": "आवेदन जमा किया",
        "tr_status_user_reported": "मैंने स्वयं बताया (ऐप के बाहर आवेदन किया)",
        "cat_potential": "संभावित रूप से पात्र",
        "cat_needs": "अधिक जानकारी आवश्यक",
        "cat_not": "पात्र नहीं",
        "cat_none": "इस श्रेणी में कोई योजना नहीं है।",
        "missing_info": "जानकारी अधूरी है",
        "checklist_title": "दस्तावेज़ों की सूची",
        "link_unverified": "आधिकारिक लिंक अभी सत्यापित नहीं है। कृपया आधिकारिक पोर्टल पर यह योजना खोजें।",
        "needs_explain": "आपका राज्य, शिक्षा और आय संबंधी विवरण नियमों से मेल खाते हैं। नीचे दी गई योजनाओं के लिए दस्तावेज़ों से जाँच आवश्यक है, क्योंकि ऐप जाति, अल्पसंख्यक, आश्रित या अंक संबंधी शर्तें आपकी प्रोफ़ाइल से सत्यापित नहीं कर सकता।",
        "header_band": "योजनामित्र AI · छात्रों के लिए छात्रवृत्ति मार्गदर्शन",
        "signin_title": "साइन इन (डेमो)",
        "signin_help": "केवल डेमो: एक नाम लिखें। पासवर्ड या पहचान संख्या नहीं माँगी जाती और न सहेजी जाती है। आपका नाम केवल इस ब्राउज़र सत्र के लिए रहता है।",
        "signin_name": "प्रदर्शन नाम",
        "signin_button": "साइन इन करें",
        "signin_guest": "अतिथि के रूप में जारी रखें",
        "signed_in_as": "साइन इन किया गया",
        "signout": "साइन आउट",
        "footer_text": "यह नमूना योजना जानकारी केवल सीखने के लिए है। पात्रता, दस्तावेज़ और अंतिम तिथियाँ हमेशा आधिकारिक सरकारी पोर्टल पर जाँचें।",
        "footer_built": "योजनामित्र AI · Python + Streamlit · कोई बाहरी AI सेवा नहीं",
        "home_greeting": "नमस्ते",
    },
}

# 28 states and 8 union territories.
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir",
    "Ladakh", "Lakshadweep", "Puducherry",
]

# Stored values for the profile form dropdowns; order matches TEXTS "edu_options" / "year_options".
EDU_VALUES = ["Class 10", "Class 12", "Undergraduate", "Postgraduate", "Other"]
YEAR_VALUES = ["1st Year", "2nd Year", "3rd Year", "4th Year", "Completed"]

# Simple paths: the data file sits next to app.py in the data/ folder.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMES_PATH = os.path.join(BASE_DIR, "data", "schemes.json")


def t(key):
    """Return the text for the current language (falls back to English)."""
    lang = st.session_state.get("lang", "en")
    return TEXTS.get(lang, TEXTS["en"]).get(key, key)


def load_schemes():
    """Read the sample scheme list from data/schemes.json."""
    with open(SCHEMES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- Session state defaults (set once, on first run) ----------
# "profile" stays None until the student saves the form.
st.session_state.setdefault("profile", None)
st.session_state.setdefault("lang", "en")
st.session_state.setdefault("user_name", None)
st.session_state.setdefault("page", "home")

# ---------- Sidebar: language and navigation ----------
# Language choice: the radio shows names in their own script.
st.sidebar.markdown("### 🎓 YojanaMitra AI")
lang_choice = st.sidebar.radio(
    "Language / भाषा",
    ["English", "हिंदी"],
    horizontal=True,
)
# Save the short language code so t() can use it everywhere below.
st.session_state["lang"] = "hi" if lang_choice == "हिंदी" else "en"

with st.sidebar.expander(t("signin_title"), expanded=st.session_state["user_name"] is None):
    if st.session_state["user_name"]:
        st.write(f"{t('signed_in_as')}: **{st.session_state['user_name']}**")
        if st.button(t("signout"), key="signout_btn"):
            st.session_state["user_name"] = None
            st.rerun()
    else:
        st.caption(t("signin_help"))
        typed_name = st.text_input(t("signin_name"), key="signin_name_input", max_chars=40)
        if st.button(t("signin_button"), key="signin_btn", type="primary"):
            if typed_name.strip():
                st.session_state["user_name"] = typed_name.strip()
                st.rerun()
            else:
                st.warning(t("signin_name"))
        if st.button(t("signin_guest"), key="guest_btn"):
            st.session_state["user_name"] = "Guest"
            st.rerun()

# ---------- Top bar: brand on the left, page buttons on the right ----------
nav_keys = ["home", "profile", "schemes", "tracker"]
brand_col, *nav_cols = st.columns([2] + [1] * len(nav_keys))
with brand_col:
    st.markdown("<div class='ym-brand'>🎓 YojanaMitra AI</div>", unsafe_allow_html=True)
for col, key in zip(nav_cols, nav_keys):
    with col:
        is_active = st.session_state["page"] == key
        if st.button(t("page_" + key), key="nav_" + key, type="primary" if is_active else "secondary"):
            st.session_state["page"] = key
            st.rerun()
# Current page key; the if/elif routing below uses this variable.
page = st.session_state["page"]

# ---------- Page: Home ----------
if page == "home":
    schemes = load_schemes()
    profile = st.session_state["profile"]
    lang = st.session_state["lang"]
    init_db()
    tracked = list_statuses()
    reminders = deadline_reminders(schemes, date.today())
    # One result per scheme; only computed when a profile is saved.
    results = check_all(schemes, profile, lang) if profile else []
    status_by_id = {r["scheme_id"]: r["status"] for r in results}
    status_labels = {
        STATUS_POTENTIAL: t("status_potential"),
        STATUS_NOT_MATCHED: t("status_not_matched"),
        STATUS_NEEDS_VERIFICATION: t("status_needs_verification"),
    }

    # Header band across the full width.
    st.markdown(t("header_band"))
    st.title(t("home_title"))

    left, center, right = st.columns([1.1, 2.4, 1.3], gap="medium")

    # LEFT: profile status only.
    with left:
        with st.container(border=True):
            st.markdown(f"**{t('card_profile')}**")
            pill_text = t("card_profile_saved") if profile else t("card_profile_missing")
            st.markdown(f"<span class='ym-pill'>{pill_text}</span>", unsafe_allow_html=True)

    # CENTER: stat cards, overview chart and scheme cards.
    with center:
        if st.session_state["user_name"]:
            st.write(f"{t('home_greeting')}, **{st.session_state['user_name']}**")
        st.write(t("home_intro"))

        potential_count = (
            sum(1 for r in results if r["status"] == STATUS_POTENTIAL) if profile else "—"
        )
        stats = [
            (len(schemes), t("card_schemes")),
            (potential_count, t("status_potential")),
            (len(tracked), t("page_tracker")),
            (len(reminders), "Upcoming deadlines"),
        ]
        stat_cols = st.columns(4)
        for col, (value, label) in zip(stat_cols, stats):
            with col:
                with st.container(border=True):
                    st.markdown(
                        f"<div class='ym-stat-value'>{value}</div>"
                        f"<div class='ym-stat-label'>{label}</div>",
                        unsafe_allow_html=True,
                    )

        with st.container(border=True):
            st.markdown("**Scheme overview**")
            if profile:
                import pandas as pd
                counts = {
                    t("status_potential"): sum(1 for r in results if r["status"] == STATUS_POTENTIAL),
                    t("status_needs_verification"): sum(1 for r in results if r["status"] == STATUS_NEEDS_VERIFICATION),
                    t("status_not_matched"): sum(1 for r in results if r["status"] == STATUS_NOT_MATCHED),
                }
                st.bar_chart(pd.DataFrame({"Schemes": list(counts.values())}, index=list(counts.keys())))
            else:
                st.info(t("no_profile"))

        st.subheader(t("page_schemes"))
        for scheme in schemes[:4]:
            name = scheme["name_hi"] if lang == "hi" and scheme.get("name_hi") else scheme["name_en"]
            description = (
                scheme["description_hi"]
                if lang == "hi" and scheme.get("description_hi")
                else scheme["description_en"]
            )
            with st.container(border=True):
                st.markdown(f"**{name}**")
                st.write(description)
                if profile:
                    status = status_by_id.get(scheme["id"])
                    pill = status_labels.get(status, t("status_needs_verification"))
                    st.markdown(f"<span class='ym-pill'>{pill}</span>", unsafe_allow_html=True)
                else:
                    st.caption(t("no_profile"))
                # Official link only when it has been verified.
                if scheme.get("link_verified") is True and scheme.get("official_link"):
                    st.link_button(t("link"), scheme["official_link"])

    # RIGHT: real deadline reminders and the stored profile fields.
    with right:
        with st.container(border=True):
            st.markdown("**Notifications**")
            if reminders:
                for item in reminders:
                    st.write(t("tr_deadline_line").format(
                        scheme_id=item["scheme_id"],
                        deadline=item["deadline"],
                        days_left=item["days_left"],
                    ))
            else:
                st.caption(t("tr_no_deadlines"))
        with st.container(border=True):
            st.markdown("**Student profile**")
            if profile:
                st.markdown(
                    f"- **{t('state')}:** {profile['state'] or '-'}\n"
                    f"- **{t('education')}:** {profile['education'] or '-'}\n"
                    f"- **{t('course')}:** {profile['course'] or '-'}\n"
                    f"- **{t('income')}:** "
                    + (f"₹{profile['income']:,}" if profile["income"] is not None else "-")
                )
            else:
                st.write(t("no_profile"))



# ---------- Page: Student Profile ----------
elif page == "profile":
    st.title(t("profile_title"))
    st.write(t("profile_intro"))

    # ---------- Natural-language input (English or Hindi text) ----------
    # Extract fields from free text, then ask the student to confirm before anything is saved.
    st.subheader(t("nl_title"))
    st.write(t("nl_intro"))
    st.text_area(
        t("nl_title"),
        key="nl_text",
        placeholder=t("nl_placeholder"),
        label_visibility="collapsed",
    )
    if st.button(t("nl_button"), key="nl_extract_btn"):
        # Only store the extraction result here; the profile is saved after confirmation.
        st.session_state["nl_extracted"] = extract_profile_from_text(st.session_state.get("nl_text", ""))

    if "nl_extracted" in st.session_state:
        extracted = st.session_state["nl_extracted"]
        ext_state = extracted.get("state")
        ext_edu = extracted.get("education")
        ext_income = extracted.get("income")

        # Index 0 is the "not found" placeholder; a missing value is never guessed.
        state_options = [t("nl_not_found")] + STATES
        edu_options = [t("nl_not_found"), "Class 10", "Class 12", "Undergraduate", "Postgraduate", "Other"]
        state_index = STATES.index(ext_state) + 1 if ext_state in STATES else 0
        edu_index = edu_options.index(ext_edu) if ext_edu in edu_options[1:] else 0

        with st.form("nl_confirm_form"):
            st.markdown(f"**{t('nl_confirm_title')}**")
            st.caption(t("nl_found_hint"))
            state_sel = st.selectbox(t("state"), state_options, index=state_index)
            edu_sel = st.selectbox(t("education"), edu_options, index=edu_index)
            income_found = st.checkbox(t("nl_income_found"), value=ext_income is not None)
            income_val = st.number_input(
                t("income"),
                min_value=0,
                step=10000,
                value=int(ext_income) if ext_income is not None else 0,
            )
            confirm = st.form_submit_button(t("nl_confirm_button"))

        if confirm:
            # Keep course and year from the existing profile; do not guess them.
            existing = st.session_state.get("profile") or {}
            st.session_state["profile"] = {
                "state": None if state_sel == t("nl_not_found") else state_sel,
                "education": None if edu_sel == t("nl_not_found") else edu_sel,
                "course": existing.get("course", ""),
                "year": existing.get("year"),
                "income": int(income_val) if income_found else None,
            }
            del st.session_state["nl_extracted"]
            st.success(t("nl_saved"))

    st.divider()

    # Form: widgets are sent to Python only when the submit button is clicked.
    with st.form("profile_form"):
        # Placeholder means "not chosen"; it is saved as None, never guessed.
        state_opts = [t("not_selected")] + STATES
        state_pick = st.selectbox(t("state"), state_opts, index=0)
        state = None if state_pick == t("not_selected") else state_pick
        edu_pick = st.selectbox(t("education"), [t("not_selected")] + list(EDU_VALUES), index=0, format_func=lambda v: v if v == t("not_selected") else t("edu_options")[EDU_VALUES.index(v)])
        education = None if edu_pick == t("not_selected") else edu_pick
        course = st.text_input(t("course"))
        year_pick = st.selectbox(t("year"), [t("not_selected")] + list(YEAR_VALUES), index=0, format_func=lambda v: v if v == t("not_selected") else t("year_options")[YEAR_VALUES.index(v)])
        year = None if year_pick == t("not_selected") else year_pick
        income = st.number_input(t("income"), min_value=0, step=10000, value=None)
        submitted = st.form_submit_button(t("save"))

    # When saved, store the values in session state.
    if submitted:
        st.session_state["profile"] = {
            "state": state,
            "education": education,
            "course": course,
            "year": year,
            "income": int(income) if income is not None else None,
        }
        st.success(t("saved_ok"))

    # Show the saved profile below the form, if there is one.
    st.subheader(t("saved_summary"))
    profile = st.session_state["profile"]
    if profile:
        st.markdown(
            f"- **{t('state')}:** {profile['state'] or '-'}\n"
            f"- **{t('education')}:** {profile['education'] or '-'}\n"
            f"- **{t('course')}:** {profile['course'] or '-'}\n"
            f"- **{t('year')}:** {profile['year'] or '-'}\n"
            f"- **{t('income')}:** "
            + (f"₹{profile['income']:,}" if profile["income"] is not None else "-")
        )
    else:
        st.info(t("no_profile"))

# ---------- Page: Schemes ----------
elif page == "schemes":
    st.title(t("schemes_title"))
    st.write(t("schemes_intro"))

    schemes = load_schemes()
    if not schemes:
        st.info(t("no_schemes"))

    lang = st.session_state["lang"]
    profile = st.session_state.get("profile")
    # One result per scheme, same order as schemes. Missing info is never a match.
    results = check_all(schemes, profile, lang)

    # Three groups, shown in this order.
    groups = [
        (STATUS_POTENTIAL, t("cat_potential")),
        (STATUS_NEEDS_VERIFICATION, t("cat_needs")),
        (STATUS_NOT_MATCHED, t("cat_not")),
    ]
    # Names of profile fields, shown to the student when they are missing.
    field_labels = {"state": t("state"), "education": t("education"), "income": t("income"), "course": t("course")}
    symbols = {"pass": "✅ ", "fail": "❌ ", "unknown": "❔ "}

    for status, heading in groups:
        st.subheader(heading)
        # Explain the "needs verification" group in plain words.
        if status == STATUS_NEEDS_VERIFICATION:
            st.caption(t("needs_explain"))
        # Pick the schemes in this group, keeping their order.
        shown = [(scheme, result) for scheme, result in zip(schemes, results) if result["status"] == status]
        if not shown:
            st.caption(t("cat_none"))
        for scheme, result in shown:
            name = scheme["name_hi"] if lang == "hi" else scheme["name_en"]
            description = scheme["description_hi"] if lang == "hi" else scheme["description_en"]
            with st.expander(name):
                st.write(description)
                st.markdown(f"**{t('ministry')}:** {scheme['ministry']}")
                # Show the official link only when it has been verified.
                if scheme.get("link_verified") is True:
                    st.markdown(f"**{t('link')}:** [{scheme['official_link']}]({scheme['official_link']})")
                else:
                    st.caption(t("link_unverified"))

                # Exact reason for every decision.
                for reason in result["reasons"]:
                    st.markdown(symbols[reason["result"]] + reason["text"])

                # Which profile details are still missing for this scheme.
                missing = missing_fields(scheme, profile)
                if missing:
                    labels = ", ".join(field_labels[m] for m in missing)
                    st.info(f"{t('missing_info')}: {labels}")

                # Document checklist only for potential matches.
                if status == STATUS_POTENTIAL:
                    checklist = build_checklist(scheme, lang)
                    st.markdown(f"**{t('checklist_title')}**")
                    for doc in checklist["documents"]:
                        st.markdown("- " + doc)
                    st.caption(checklist["note"])

# ---------- Page: Tracker ----------
elif page == "tracker":
    st.title(t("tr_title"))
    st.write(t("tr_intro"))

    schemes = load_schemes()
    lang = st.session_state["lang"]

    # a. Deadline reminders from verified scheme deadlines.
    reminders = deadline_reminders(schemes, date.today())
    if not reminders:
        st.info(t("tr_no_deadlines"))
    for item in reminders:
        st.warning(t("tr_deadline_line").format(
            scheme_id=item["scheme_id"],
            deadline=item["deadline"],
            days_left=item["days_left"],
        ))

    # b. Personalised document checklist, based on the eligibility results.
    profile = st.session_state.get("profile")
    results = check_all(schemes, profile, lang)
    statuses = {r["scheme_id"]: r["status"] for r in results}
    checklists = build_checklists(schemes, statuses, lang)
    st.subheader(t("tr_checklist_title"))
    if not checklists:
        st.info(t("tr_no_checklist"))
    for checklist in checklists:
        with st.expander(checklist["scheme_id"]):
            for doc in checklist["documents"]:
                st.markdown("- " + doc)
            st.caption(checklist["note"])

    # c. Application status, saved in SQLite.
    init_db()
    current = list_statuses()
    status_options = [STATUS_DISCOVERED, STATUS_DOCS_PENDING, STATUS_SUBMITTED, STATUS_USER_REPORTED]
    status_labels = {
        STATUS_DISCOVERED: t("tr_status_discovered"),
        STATUS_DOCS_PENDING: t("tr_status_docs_pending"),
        STATUS_SUBMITTED: t("tr_status_submitted"),
        STATUS_USER_REPORTED: t("tr_status_user_reported"),
    }
    st.subheader(t("tr_status_title"))
    for checklist in checklists:
        scheme_id = checklist["scheme_id"]
        # Default to the saved status if there is one, otherwise "discovered".
        current_status = current.get(scheme_id, STATUS_DISCOVERED)
        chosen = st.selectbox(
            scheme_id,
            status_options,
            index=status_options.index(current_status) if current_status in status_options else 0,
            key="status_" + scheme_id,
            format_func=lambda s: status_labels.get(s, s),
        )
        if st.button(t("tr_save_button"), key="save_" + scheme_id):
            set_status(scheme_id, chosen)
            st.success(t("tr_saved"))

st.divider()
st.caption(t("footer_text"))
st.caption(t("footer_built"))
