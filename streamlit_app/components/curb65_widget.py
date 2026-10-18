import streamlit as st

def render_curb65():
    """
    Renders the CURB-65 Pneumonia Severity Calculator.
    Returns the calculated score (int).
    """
    with st.expander("Pneumonia Severity (CURB-65)", expanded=True):
        st.caption("Assess severity to guide disposition (Admission vs. Home).")
        
        col1, col2 = st.columns(2)
        
        with col1:
            confusion = st.checkbox("Confusion (new onset)", key="curb_c")
            rr = st.checkbox("Respiratory rate ≥ 30/min", key="curb_r")
            age = st.checkbox("Age ≥ 65 years", key="curb_age")
            
        with col2:
            urea = st.checkbox("Urea > 7 mmol/L (BUN > 19 mg/dL)", key="curb_u")
            bp = st.checkbox("BP < 90 Sys or ≤ 60 Dia", key="curb_b")
            
        # Calculate Score
        score = sum([confusion, urea, rr, bp, age])
        
        if score <= 1:
            st.success(f"**LOW RISK (Score {score})**\nConsider outpatient treatment.")
        elif score == 2:
            st.warning(f"**MODERATE RISK (Score {score})**\nConsider hospital admission or short-stay unit.")
        else:
            st.error(f"**HIGH RISK (Score {score})**\nAdmit to hospital. Assess for ICU if score is 4-5.")
            
        return score