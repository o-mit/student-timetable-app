import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
import datetime
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

# PDF day/date/timeslot-aware parser
def parse_pdf_to_schedule(pdf_bytes):
    time_slots = [
        "9:30 - 10:45 am", "11:00 am -12:15 pm", "12:30 - 01:45 pm",
        "02:30 - 3:45 pm", "4:00 -5:15 pm", "5:45-7:00 pm", "7:15-8:30 pm"
    ]
    week_dates = {
        "Mon": "21 Jul 2025", "Tue": "22 Jul 2025", "Wed": "23 Jul 2025",
        "Thu": "24 Jul 2025", "Fri": "25 Jul 2025", "Sat": "26 Jul 2025", "Sun": "27 Jul 2025"
    }

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    lines = text.splitlines()

    schedule = []
    current_day = None
    current_date = None
    row_idx = -1

    for line in lines:
        for abbr, date in week_dates.items():
            if abbr in line:
                current_day = datetime.datetime.strptime(date, "%d %b %Y").strftime("%A")
                current_date = date
                row_idx = 0
                break

        if current_day is None or len(line.strip()) < 4:
            continue

        pattern = re.compile(r"([A-Z]{2,5})-([A-Z])\(\d+\)-([A-Z]+)\s*\{([^}]+)\}")
        matches = pattern.findall(line)

        if matches:
            time_slot = time_slots[min(row_idx, len(time_slots)-1)]
            for m in matches:
                schedule.append({
                    "day": current_day,
                    "date": current_date,
                    "time": time_slot,
                    "course_abbr": m[0],
                    "section": m[1],
                    "faculty": m[2],
                    "venue": m[3]
                })
            row_idx += 1

    return schedule

# Filter by selection and enrich

def filter_schedule(sessions, selected, info_map):
    final = []
    for s in sessions:
        key = (s["course_abbr"], s["section"])
        if key in selected:
            final.append({
                "Day": s["day"],
                "Date": s["date"],
                "Time Slot": s["time"],
                "Subject": info_map[key]["course_name"],
                "Faculty": s["faculty"],
                "Venue": s["venue"]
            })
    return final

# Show results
if pdf_file and user_selection:
    raw_schedule = parse_pdf_to_schedule(pdf_file.read())
    personal_schedule = filter_schedule(raw_schedule, user_selection, course_info)

    if personal_schedule:
        st.success("Here is your personalized schedule:")
        st.dataframe(pd.DataFrame(personal_schedule), use_container_width=True)
    else:
        st.warning("No matching classes found in the uploaded timetable.")

elif pdf_file and not user_selection:
    st.warning("Please select your courses first from the sidebar.")

elif user_selection and not pdf_file:
    st.info("Upload your weekly timetable PDF to generate your schedule.")
