from pathlib import Path
import base64
import streamlit as st
import streamlit.components.v1 as components

from backend.backend_utils.subscription_utils import (
    get_active_subscription_plans,
)
from streamlit_app.auth.client_application import (
    show_client_application,
    clear_application,
)
from shared.assets import load_css, image_path


LOGO_FILE = "LungSight_Logo-nobg.png"
HERO_IMAGE_FILE = "hero_xray_preview.jpg"


# ============================================================
# HELPERS
# ============================================================

def peso(amount):
    return f"\u20b1{float(amount or 0):,.2f}"


def limit_text(value):
    return "Unlimited" if value is None else f"{value:,}"


@st.cache_data(show_spinner=False)
def image_as_base64(path):
    try:
        p = Path(path)
        if not p.exists():
            return None
        encoded = base64.b64encode(p.read_bytes()).decode("utf-8")
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(p.suffix.lower(), "image/jpeg")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return None


def go_to_login():
    st.session_state["public_page"] = "login"
    st.rerun()


# ============================================================
# UNIFIED FLOATING NAVBAR
# ============================================================

def show_navbar():
    logo_file = image_path(LOGO_FILE)
    logo_data = image_as_base64(logo_file)
    logo_tag = (
        f"<img src='{logo_data}' class='ls-nav-logo-img' alt='LungSight Logo'/>"
        if logo_data
        else "<span class='material-symbols-rounded ls-nav-fallback-icon'>radiology</span>"
    )

    with st.container(key="homepage_navbar"):
        nav_brand, nav_links, nav_cta = st.columns([2.8, 5.6, 1.6], gap="small", vertical_alignment="center")

        with nav_brand:
            brand_html = (
                "<div class='ls-nav-brand'>"
                f"{logo_tag}"
                "<span class='ls-nav-title'>LungSight</span>"
                "<div class='ls-nav-tag'>"
                "<span class='material-symbols-rounded'>verified</span>"
                "<span>Clinical AI</span>"
                "</div>"
                "</div>"
            )
            st.markdown(brand_html, unsafe_allow_html=True)

        with nav_links:
            links_html = (
                "<div class='ls-nav-links'>"
                "<a class='ls-nav-link' href='#features'>Features</a>"
                "<a class='ls-nav-link' href='#workflow'>Workflow</a>"
                "<a class='ls-nav-link' href='#plans'>Hospital Plans</a>"
                "<a class='ls-nav-link' href='#about'>About Us</a>"
                "<a class='ls-nav-link' href='#trust'>Security</a>"
                "</div>"
            )
            st.markdown(links_html, unsafe_allow_html=True)

        with nav_cta:
            with st.container(key="nav_signin_btn"):
                if st.button("Sign In to Portal", key="btn_nav_signin", width="stretch"):
                    go_to_login()


# ============================================================
# HERO SECTION
# ============================================================

def show_hero():
    with st.container(key="hero_container"):
        hero_left, hero_right = st.columns([1.15, 0.85], gap="large", vertical_alignment="center")

        with hero_left:
            hero_text_html = (
                "<div class='ls-hero-kicker-pill'>"
                "<div class='ls-hero-beacon'></div>"
                "<span>Institutional Radiology Decision Support</span>"
                "</div>"
                "<h1 class='ls-hero-title'>Smarter Chest X-Ray Screening for <span>Modern Hospitals</span></h1>"
                "<p class='ls-hero-subtitle'>AI-assisted pulmonary triage and presumptive pneumonia localization engineered to empower hospital imaging teams, accelerate radiologist reviews, and elevate patient care.</p>"
            )
            st.markdown(hero_text_html, unsafe_allow_html=True)

            cta_cols = st.columns([1.2, 1.1], gap="medium")
            with cta_cols[0]:
                with st.container(key="hero_portal_btn"):
                    if st.button("Access Staff Portal", key="btn_hero_portal", width="stretch"):
                        go_to_login()

            with cta_cols[1]:
                with st.container(key="hero_plans_btn"):
                    if st.button("Explore Hospital Plans", key="btn_hero_plans", width="stretch"):
                        st.session_state["scroll_to_plans"] = True
                        st.rerun()

            metrics_html = (
                "<div class='ls-hero-metrics'>"
                "<div class='ls-metric-item'><b>89.2%+</b><span>Diagnostic Sensitivity</span></div>"
                "<div class='ls-metric-item'><b>&lt; 3.2s</b><span>Triage Latency</span></div>"
                "<div class='ls-metric-item'><b>256-Bit</b><span>RLS Data Isolation</span></div>"
                "</div>"
            )
            st.markdown(metrics_html, unsafe_allow_html=True)

        with hero_right:
            hero_img_file = image_path(HERO_IMAGE_FILE)
            hero_img_data = image_as_base64(hero_img_file)
            img_src = hero_img_data if hero_img_data else ""

            hero_card_html = (
                "<div class='ls-hero-image-card'>"
                f"<img src='{img_src}' alt='LungSight AI Chest X-Ray Diagnostic Station'/>"
                "<div class='ls-hero-floating-badge'>"
                "<div class='ls-hero-badge-left'>"
                "<div class='ls-hero-badge-icon'><span class='material-symbols-rounded'>biotech</span></div>"
                "<div class='ls-hero-badge-text'><b>ResNet-50 Diagnostic Engine</b><span>Active AI Localization &bull; CXR Triage</span></div>"
                "</div>"
                "<div class='ls-hero-badge-tag'>Online</div>"
                "</div>"
                "</div>"
            )
            st.markdown(hero_card_html, unsafe_allow_html=True)


# ============================================================
# FEATURES SECTION (The 4 Clinical Pillars)
# ============================================================

def show_features():
    header_html = (
        "<div id='features' class='ls-section-header' style='scroll-margin-top: 50px; text-align: center !important;'>"
        "<span class='ls-section-kicker' style='text-align: center !important;'>CLINICAL EXCELLENCE</span>"
        "<h2 class='ls-section-title' style='text-align: center !important;'>Engineered for Hospital Imaging Workflows</h2>"
        "<p class='ls-section-desc' style='text-align: center !important; margin: 0 auto !important;'>Purpose-built clinical decision tools designed to eliminate triage bottlenecks while preserving strict physician oversight.</p>"
        "</div>"
    )

    features_data = [
        (
            "radiology",
            "Automated CXR Triage",
            "Instant anomaly localization flags presumptive pneumonia and suspicious opacities in real time before formal review.",
        ),
        (
            "verified",
            "ResNet-50 AI Engine",
            "Deep-learning model calibrated on validated clinical radiographs, generating probabilistic lesion heatmaps.",
        ),
        (
            "task_alt",
            "Physician-Validated",
            "Collaborative radiologist review tools with DICOM controls, differential findings, and certified digital sign-offs.",
        ),
        (
            "event_available",
            "Patient Care Tracker",
            "Longitudinal patient monitoring and scheduled follow-ups to track pulmonary treatment response over time.",
        ),
    ]

    cards_html = "".join(
        "<div class='ls-feature-card' style='text-align: center !important; align-items: center !important; justify-content: center !important; display: flex !important; flex-direction: column !important; box-sizing: border-box !important;'>"
        f"<div class='ls-feature-icon-box' style='margin: 0 auto 1.2rem auto !important; display: flex !important; align-items: center !important; justify-content: center !important;'><span class='material-symbols-rounded'>{icon}</span></div>"
        f"<h3 style='text-align: center !important; justify-content: center !important; align-items: center !important; width: 100% !important; display: flex !important; margin: 0 auto 0.7rem auto !important;'>{title}</h3>"
        f"<p style='text-align: center !important; margin: 0 auto !important; width: 100% !important;'>{desc}</p>"
        "</div>"
        for icon, title, desc in features_data
    )

    full_html = (
        f"{header_html}"
        f"<div class='ls-features-grid'>{cards_html}</div>"
    )

    with st.container(key="features_section"):
        st.markdown(full_html, unsafe_allow_html=True)


# ============================================================
# HOW IT WORKS (3-Step Pipeline)
# ============================================================

def show_pipeline():
    with st.container(key="pipeline_section"):
        header_html = (
            "<div id='workflow' class='ls-section-header' style='scroll-margin-top: 50px; text-align: center !important;'>"
            "<span class='ls-section-kicker' style='background:rgba(35,210,229,0.14);border-color:rgba(35,210,229,0.3);color:#A8EEF9; text-align: center !important;'>WORKFLOW PIPELINE</span>"
            "<h2 class='ls-section-title' style='color:#FFFFFF !important; text-align: center !important;'>From Image Acquisition to Verified Report</h2>"
            "<p class='ls-section-desc' style='color:var(--text-dark-dim) !important; text-align: center !important; margin: 0 auto !important;'>A seamless, three-phase clinical workflow designed for speed, security, and diagnostic precision.</p>"
            "</div>"
        )

        steps_data = [
            (
                "01 / INGESTION",
                "DICOM & X-Ray Ingestion",
                "Radiologic technologists upload chest radiographs. Automatic contrast normalization and metadata validation prepare the image for immediate processing.",
            ),
            (
                "02 / INFERENCE",
                "Deep Learning Inference",
                "The calibrated neural engine analyzes bilateral lung fields in under 3.2 seconds, generating localization bounding boxes and diagnostic confidence indices.",
            ),
            (
                "03 / VALIDATION",
                "Radiologist Review & Sign-Off",
                "Licensed radiologists review heatmap overlays, annotate findings, cross-reference clinical notes, and electronically authorize the final medical report.",
            ),
        ]

        steps_html = "".join(
            "<div class='ls-step-card' style='text-align: center !important; align-items: center !important; justify-content: center !important; display: flex !important; flex-direction: column !important; box-sizing: border-box !important;'>"
            f"<span class='ls-step-number' style='margin: 0 auto 1.2rem auto !important; display: inline-flex !important; align-items: center !important; justify-content: center !important;'>{num}</span>"
            f"<h3 style='text-align: center !important; justify-content: center !important; align-items: center !important; width: 100% !important; display: flex !important; margin: 0 auto 0.8rem auto !important;'>{title}</h3>"
            f"<p style='text-align: center !important; margin: 0 auto !important; width: 100% !important;'>{desc}</p>"
            "</div>"
            for num, title, desc in steps_data
        )

        full_html = (
            f"{header_html}"
            f"<div class='ls-pipeline-grid'>{steps_html}</div>"
        )
        st.markdown(full_html, unsafe_allow_html=True)


# ============================================================
# HOSPITAL SUBSCRIPTION PLANS (Transferred from login.css)
# ============================================================

def show_plan_card(plan):
    plan_id = plan["plan_id"]
    plan_name = plan.get("plan_name") or "LungSight Plan"
    description = plan.get("description") or "Complete institutional pulmonary intelligence tier."

    users = limit_text(plan.get("max_users"))
    patients = limit_text(plan.get("max_patients"))
    xrays = limit_text(plan.get("max_xrays_per_month"))

    monthly = peso(plan.get("price_monthly"))
    yearly = peso(plan.get("price_yearly"))

    is_popular = "professional" in plan_name.lower()
    popular_badge = (
        "<div class='ls-plan-popular-badge'>"
        "<span class='material-symbols-rounded'>star</span>"
        "<span>RECOMMENDED</span>"
        "</div>"
        if is_popular
        else ""
    )

    features = (
        f"<div class='ls-plan-feature'><span>Staff Users</span><b>{users}</b></div>"
        f"<div class='ls-plan-feature'><span>Patient Records</span><b>{patients}</b></div>"
        f"<div class='ls-plan-feature'><span>X-rays / month</span><b>{xrays}</b></div>"
        "<div class='ls-plan-feature'><span>ResNet-50 Engine</span><b>Included</b></div>"
    )

    card_html = (
        f"{popular_badge}"
        "<div class='ls-plan-icon' style='margin: 0 auto 1.4rem auto !important; display: flex !important; align-items: center !important; justify-content: center !important;'><span class='material-symbols-rounded'>layers</span></div>"
        f"<p class='ls-plan-name' style='text-align: center !important; margin: 0 !important;'>{plan_name}</p>"
        f"<p class='ls-plan-desc' style='text-align: center !important; margin: 0.55rem auto 1.4rem auto !important;'>{description}</p>"
        "<div class='ls-plan-price-row' style='justify-content: center !important; text-align: center !important; margin: 0 auto !important; display: flex !important;'>"
        f"<p class='ls-plan-price' style='text-align: center !important;'>{monthly}</p>"
        "<span>/ month</span>"
        "</div>"
        f"<p class='ls-plan-yearly' style='text-align: center !important; margin: 0.35rem auto 1.5rem auto !important;'>or {yearly} per year</p>"
        f"<div class='ls-plan-features'>{features}</div>"
    )

    card_key = f"plan_card_{plan_id}_popular" if is_popular else f"plan_card_{plan_id}"

    with st.container(key=card_key):
        st.markdown(card_html, unsafe_allow_html=True)
        btn_label = "Select plan"
        if st.button(btn_label, key=f"select_plan_{plan_id}", width="stretch"):
            clear_application()
            st.session_state["selected_plan_id"] = plan_id
            st.session_state["show_application_form"] = True
            st.rerun()


def show_hospital_plans():
    header_html = (
        "<div id='plans' class='ls-subscriptions-header' style='scroll-margin-top: 50px; text-align: center !important;'>"
        "<p class='ls-subscriptions-kicker' style='text-align: center !important; margin: 0 auto 0.8rem auto !important;'>SUBSCRIPTION PLANS</p>"
        "<p class='ls-subscriptions-title' style='text-align: center !important; margin: 0.4rem auto 0.8rem auto !important;'>Choose a plan for your hospital</p>"
        "<p class='ls-subscriptions-subtitle' style='text-align: center !important; margin: 0 auto !important;'>Scalable pulmonary AI infrastructure for healthcare centers of any size.</p>"
        "</div>"
    )
    st.markdown(header_html, unsafe_allow_html=True)

    plans = get_active_subscription_plans()

    if not plans:
        st.info("Subscription plans are currently being updated.")
        return

    with st.container(key="subscriptions_section"):
        cols = st.columns(len(plans), gap="large")
        for col, plan in zip(cols, plans):
            with col:
                show_plan_card(plan)

    # APPLICATION FORM (opens directly when "Select plan" is clicked)
    show_application(plans)


def show_application(plans):
    if not st.session_state.get("show_application_form"):
        return

    selected_id = st.session_state.get("selected_plan_id")
    for plan in plans:
        if plan["plan_id"] == selected_id:
            st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
            show_client_application(plan)
            return


# ============================================================
# ABOUT US SECTION (Transferred from login & elevated)
# ============================================================

def show_about_us():
    about_html = (
        "<div class='ls-about-section'>"
        "<div id='about' class='ls-section-header' style='scroll-margin-top: 50px; text-align: center !important;'>"
        "<span class='ls-section-kicker' style='text-align: center !important;'>ABOUT LUNGSIGHT</span>"
        "<h2 class='ls-section-title' style='text-align: center !important;'>Advancing Pulmonary Healthcare Through AI</h2>"
        "<p class='ls-section-desc' style='text-align: center !important; margin: 0 auto !important;'>Pioneering physician-centered deep learning technologies to eliminate diagnostic delays and elevate patient care globally.</p>"
        "</div>"
        "<div class='ls-about-grid'>"
        "<div class='ls-about-card' style='text-align: center !important; align-items: center !important; justify-content: center !important; display: flex !important; flex-direction: column !important; box-sizing: border-box !important;'>"
        "<div class='ls-about-icon' style='margin: 0 auto 1.2rem auto !important; display: flex !important; align-items: center !important; justify-content: center !important;'><span class='material-symbols-rounded'>clinical_notes</span></div>"
        "<h3 style='text-align: center !important; justify-content: center !important; align-items: center !important; width: 100% !important; display: flex !important; margin: 0 auto 0.8rem auto !important;'>Our Clinical Mission</h3>"
        "<p style='text-align: center !important; margin: 0 auto !important;'>Pneumonia and acute pulmonary conditions remain leading causes of avoidable hospital mortality. LungSight was engineered alongside thoracic radiologists to provide rapid, high-confidence presumptive triage, empowering clinicians during critical diagnostic windows.</p>"
        "</div>"
        "<div class='ls-about-card' style='text-align: center !important; align-items: center !important; justify-content: center !important; display: flex !important; flex-direction: column !important; box-sizing: border-box !important;'>"
        "<div class='ls-about-icon' style='margin: 0 auto 1.2rem auto !important; display: flex !important; align-items: center !important; justify-content: center !important;'><span class='material-symbols-rounded'>diversity_1</span></div>"
        "<h3 style='text-align: center !important; justify-content: center !important; align-items: center !important; width: 100% !important; display: flex !important; margin: 0 auto 0.8rem auto !important;'>Radiologist-in-the-Loop</h3>"
        "<p style='text-align: center !important; margin: 0 auto !important;'>We strictly adhere to ethical, physician-centered AI principles. LungSight serves as an intelligent co-pilot that highlights regions of interest and accelerates differential analysis, leaving all clinical decisions in the hands of certified medical doctors.</p>"
        "</div>"
        "<div class='ls-about-card' style='text-align: center !important; align-items: center !important; justify-content: center !important; display: flex !important; flex-direction: column !important; box-sizing: border-box !important;'>"
        "<div class='ls-about-icon' style='margin: 0 auto 1.2rem auto !important; display: flex !important; align-items: center !important; justify-content: center !important;'><span class='material-symbols-rounded'>domain_add</span></div>"
        "<h3 style='text-align: center !important; justify-content: center !important; align-items: center !important; width: 100% !important; display: flex !important; margin: 0 auto 0.8rem auto !important;'>Accessible Healthcare</h3>"
        "<p style='text-align: center !important; margin: 0 auto !important;'>From major tertiary medical centers to rural community clinics, LungSight levels the diagnostic playing field by delivering cutting-edge computer vision to imaging teams everywhere, ensuring rapid care regardless of hospital resource limitations.</p>"
        "</div>"
        "</div>"
        "</div>"
    )
    st.markdown(about_html, unsafe_allow_html=True)


# ============================================================
# TRUST, SECURITY & COMPLIANCE
# ============================================================

def show_trust_section():
    header_html = (
        "<div id='trust' class='ls-section-header' style='scroll-margin-top: 50px; text-align: center !important;'>"
        "<span class='ls-section-kicker' style='text-align: center !important;'>GOVERNANCE & TRUST</span>"
        "<h2 class='ls-section-title' style='text-align: center !important;'>Enterprise Clinical Security</h2>"
        "<p class='ls-section-desc' style='text-align: center !important; margin: 0 auto !important;'>Engineered from the ground up to protect confidential patient health data and support hospital compliance.</p>"
        "</div>"
    )

    trust_items = [
        (
            "lock",
            "256-Bit SSL Encryption",
            "End-to-end cryptographic transit security protects every X-ray image and patient record.",
        ),
        (
            "shield",
            "Row-Level Security",
            "Isolated database partitions guarantee total data separation between hospital tenants.",
        ),
        (
            "medical_services",
            "Physician-in-the-Loop",
            "AI findings serve strictly as supportive decision aids under certified physician control.",
        ),
        (
            "policy",
            "Complete Audit Trail",
            "Tamper-resistant audit logs track every sign-off, diagnosis amendment, and image review.",
        ),
    ]

    cards_html = "".join(
        "<div class='ls-trust-card' style='text-align: center !important; align-items: center !important; justify-content: center !important; display: flex !important; flex-direction: column !important; box-sizing: border-box !important;'>"
        f"<div class='ls-trust-icon' style='margin: 0 auto 0.9rem auto !important; display: flex !important; align-items: center !important; justify-content: center !important;'><span class='material-symbols-rounded'>{icon}</span></div>"
        f"<h4 style='text-align: center !important; justify-content: center !important; align-items: center !important; width: 100% !important; display: flex !important; margin: 0 auto 0.5rem auto !important;'>{title}</h4>"
        f"<p style='text-align: center !important; margin: 0 auto !important; width: 100% !important;'>{desc}</p>"
        "</div>"
        for icon, title, desc in trust_items
    )

    full_html = (
        f"{header_html}"
        f"<div class='ls-trust-grid'>{cards_html}</div>"
    )

    with st.container(key="trust_section"):
        st.markdown(full_html, unsafe_allow_html=True)


# ============================================================
# CTA BANNER
# ============================================================

def show_cta_banner():
    with st.container(key="cta_banner"):
        cta_html = (
            "<h2>Ready to Accelerate Your Hospital's Radiology Workflow?</h2>"
            "<p>Join healthcare institutions utilizing LungSight AI to streamline presumptive pneumonia detection and support clinical imaging teams.</p>"
        )
        st.markdown(cta_html, unsafe_allow_html=True)

        _, center_col, _ = st.columns([1.6, 1.2, 1.6])
        with center_col:
            with st.container(key="cta_portal_btn"):
                if st.button("Access Clinical Portal", key="btn_cta_portal", width="stretch"):
                    go_to_login()


# ============================================================
# FOOTER
# ============================================================

def show_footer():
    footer_html = (
        "<div class='ls-hp-footer'>"
        "<div class='ls-footer-disclaimer'>"
        "<b>Clinical Regulatory Notice:</b> LungSight is an artificial intelligence-assisted clinical decision-support system intended for use by licensed physicians, radiologists, and healthcare professionals. The system provides automated presumptive findings to assist in triage and diagnostic prioritization. It does not replace independent clinical judgment, laboratory testing, or formal medical diagnosis."
        "</div>"
        "<p class='ls-footer-copyright'>&copy; 2026 LungSight Healthcare Technologies. All institutional rights reserved &bull; Institutional Radiology Portal</p>"
        "</div>"
    )
    st.markdown(footer_html, unsafe_allow_html=True)


# ============================================================
# SMOOTH SCROLL HELPER FOR ANCHOR LINKS (#features, #workflow, etc.)
# ============================================================

def inject_smooth_scroll():
    """Enable smooth scrolling while returning to the homepage top on refresh."""

    components.html(
        """
        <script>
        (function () {
            const win = window.parent;
            const doc = win.document;

            // Prevent duplicate event listeners if Streamlit reruns the component.
            if (win.__lungsightSmoothScrollInitialized) {
                return;
            }
            win.__lungsightSmoothScrollInitialized = true;

            // Detect a browser refresh.
            const navigationEntries =
                win.performance &&
                win.performance.getEntriesByType
                    ? win.performance.getEntriesByType("navigation")
                    : [];

            const navigationType = navigationEntries.length
                ? navigationEntries[0].type
                : "";

            if (navigationType === "reload") {
                // Remove the old navigation fragment after refreshing.
                win.history.replaceState(
                    null,
                    "",
                    win.location.pathname + win.location.search
                );

                // Return the page to the top.
                win.scrollTo(0, 0);
            }

            // Smoothly scroll to a section by its ID.
            function scrollToHash(hash) {
                if (!hash || hash.length <= 1) {
                    return;
                }

                let target;

                try {
                    target = doc.querySelector(hash);
                } catch (error) {
                    return;
                }

                if (target) {
                    target.scrollIntoView({
                        behavior: "smooth",
                        block: "start"
                    });
                }
            }

            // Handle the plans redirect requested by Streamlit.
            const shouldScrollToPlans =
                win.sessionStorage.getItem("lungsight_scroll_to_plans") === "true";

            if (shouldScrollToPlans) {
                win.sessionStorage.removeItem("lungsight_scroll_to_plans");

                win.requestAnimationFrame(function () {
                    scrollToHash("#plans");
                });
            } else if (navigationType !== "reload") {
                // Support direct links containing a section fragment.
                const initialHash = win.location.hash;

                if (initialHash && initialHash.length > 1) {
                    win.requestAnimationFrame(function () {
                        scrollToHash(initialHash);
                    });
                }
            }

            // Support browser navigation that changes the URL fragment.
            win.addEventListener("hashchange", function () {
                scrollToHash(win.location.hash);
            });

            // Handle clicks on the homepage navigation links.
            doc.addEventListener("click", function (event) {
                const link = event.target.closest("a.ls-nav-link");

                if (!link) {
                    return;
                }

                const href = link.getAttribute("href");

                if (!href || !href.startsWith("#")) {
                    return;
                }

                const target = doc.querySelector(href);

                if (!target) {
                    return;
                }

                // Stop the browser from performing its default jump.
                event.preventDefault();

                // Keep the URL clean instead of storing #workflow, #trust, etc.
                win.history.replaceState(
                    null,
                    "",
                    win.location.pathname + win.location.search
                );

                // Smoothly scroll to the selected section.
                target.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            });
        })();
        </script>
        """,
        height=0
    )


# ============================================================
# MAIN HOMEPAGE ENTRYPOINT
# ============================================================

def show_homepage():
    load_css("homepage.css")
    inject_smooth_scroll()
    show_navbar()
    show_hero()
    show_features()
    show_pipeline()
    show_hospital_plans()
    show_about_us()
    show_trust_section()
    show_cta_banner()
    show_footer()
