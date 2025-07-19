import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
from io import BytesIO

st.set_page_config(page_title="Student Timetable Generator", layout="wide")
st.title("📅 Personalized Timetable Generator")

# Load Course Mapping (Excel file is assumed fixed)
@st.cache_data

def load_course_data():
    df = pd.read_excel("Course and Sections.xlsx", sheet_name="Table 2")
    course_map = {}
    for _, row in df.iterrows():
        abbrev = row["Abbriviation"]
        area = row["Area"]
        full_name = row["Course Name"]
        sections = [s.strip() for s in row["Sections"].split(",")]
        for sec in sections:
            course_map[(abbrev, sec)] = {"area": area, "course_name": full_name}
    return df, course_map

course_df, course_info = load_course_data()

# UI: Course-Section Selection
st.sidebar.header("Step 1: Select Your Courses")
user_selection = []

for area in sorted(course_df["Area"].unique()):
    with st.sidebar.expander(f"📚 {area}"):
        area_df = course_df[course_df["Area"] == area]
        for _, row in area_df.iterrows():
            course = row["Abbriviation"]
            label = row["Course Name"]
            sections = row["Sections"].split(",")
            selected = st.multiselect(f"{label} ({course})", sections, key=f"{course}_{area}")
            for sec in selected:
                user_selection.append((course, sec.strip()))

# UI: PDF Upload
st.sidebar.header("Step 2: Upload Weekly Timetable PDF")
pdf_file = st.sidebar.file_uploader("Upload PDF", type=["pdf"])

# Regex parser
def parse_pdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    pattern = re.compile(r"(\b[A-Z]{2,5})-([A-Z])\(\d+\)-([A-Z]+)\s*\{([^}]+)\}")
    matches = pattern.findall(text)
    sessions = [
        {"course_abbr": m[0], "section": m[1], "faculty": m[2], "venue": m[3]}
        for m in matches
    ]
    return sessions

# Filter by selection
def filter_schedule(sessions, selected, info_map):
    schedule = []
    for s in sessions:
        key = (s["course_abbr"], s["section"])
        if key in selected:
            enriched = {
                **s,
                "course_name": info_map[key]["course_name"],
                "area": info_map[key]["area"]
            }
            schedule.append(enriched)
    return schedule

# Show results
if pdf_file and user_selection:
    sessions = parse_pdf(pdf_file.read())
    final_schedule = filter_schedule(sessions, user_selection, course_info)

    if final_schedule:
        st.success("Here is your personalized schedule:")
        df_output = pd.DataFrame(final_schedule)
        df_output = df_output[["course_name", "section", "faculty", "venue", "area"]]
        df_output.columns = ["Course", "Section", "Faculty", "Venue", "Area"]
        st.dataframe(df_output, use_container_width=True)
    else:
        st.warning("No matching classes found in the uploaded timetable.")

elif pdf_file and not user_selection:
    st.warning("Please select your courses first from the sidebar.")

elif user_selection and not pdf_file:
    st.info("Upload your weekly timetable PDF to generate your schedule.")
