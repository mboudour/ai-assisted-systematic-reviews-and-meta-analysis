"""
AI-Assisted Systematic Reviews and Meta-Analysis — instats Seminar
Main entry point for the Streamlit application.
"""
import streamlit as st

st.set_page_config(
    page_title="AI-Assisted Systematic Reviews and Meta-Analysis",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔬 AI-Assisted Systematic Reviews and Meta-Analysis")
st.subheader("instats Seminar — June 10–12, 2026")

st.markdown("""
**Moses Boudourides, Moses.Boudourides@gmail.com**

Welcome to the interactive companion for the three-day instats seminar on
**AI-Assisted Systematic Reviews and Meta-Analysis**.

This application guides you through the complete evidence synthesis pipeline —
from formulating a search strategy and collecting bibliographic records via open APIs,
to AI-assisted screening, structured data extraction from full-text PDFs, and
preliminary narrative or quantitative synthesis.

No coding is required: every operation is available through the menus on the left.

---

### How to Navigate

Use the **sidebar** to select a day:

| Day | Theme |
|-----|-------|
| **Day 1** | From Query to Corpus |
| **Day 2** | From Corpus to Included Studies |
| **Day 3** | From Studies to Evidence |

---

### Four Guided Case Studies

Each day works through four discipline-spanning examples so you can follow the
full systematic review lifecycle in a domain close to your own:

| # | Discipline | Topic |
|---|---|---|
| 1 | 🏥 Health Sciences | Health Inequalities in Chronic Disease Care |
| 2 | 🏛️ Social Sciences | Universal Basic Income (UBI) Policy Outcomes |
| 3 | ⚗️ Science / Engineering | Microplastic Pollution in Aquatic Environments |
| 4 | 💼 Management / Business | CSR and Firm Financial Performance |

---

### Resources

- 📋 [Seminar info & registration](https://instats.org/seminar/ai-assisted-systematic-reviews-and-meta)
- 💻 [Scripts and slides on GitHub](https://github.com/mboudour/ai-assisted-systematic-reviews-and-meta-analysis)
""")

st.info("👈 Select a day from the sidebar to begin.")
