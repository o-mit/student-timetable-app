import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re
import io
from collections import defaultdict

# --- Page Configuration ---
st.set_page_config(
    page_title="My Weekly Timetable",
    page_icon="🗓️",
    layout="wide"
)

# --- Regular Expression to Parse Class Details ---
# Pattern: MFS-A(6)-AB {C - 402}
# Breakdown:
# ([A-Z0-9]+)  -> Course Abbreviation (e.g., "MFS", "SMMT")
# -             -> Literal hyphen
# ([A-Z0-9]+)  -> Section (e.g., "A", "Exc")
# \((\d+)\)    -> Session number in parentheses (e.g., "(6)")
# -             -> Literal hyphen
# ([A-Z/]+)    -> Faculty Initials (e.g., "AB", "AP/PD")
# \s* -> Optional whitespace
# \{(.*?)\}     -> Venue inside curly braces (e.g., "{C - 402}")
CLASS_PATTERN = re.compile(r"([A-Z0-9]+)-([A-Z0-9]+)\((\d+)\)-([A-Z/]+)\s*\{(.*?)\}")

# --- Helper Functions ---

@st.cache_data
def load_course_data(uploaded_file):
    """Loads and processes the course and sections CSV file."""
    try:
        df = pd.read_csv(uploaded_file)
        df['Abbriviation'] = df['Abbriviation'].str.strip()
        return df
    except Exception as e:
        st.error(f"Error loading course data CSV: {e}")
        return None

def generate_selectable_courses(df):
    """Generates a list of 'Course-Section' strings for the user to select."""
    selectable_list = []
    for _, row in df.iterrows():
        abbr = row['Abbriviation']
        sections = str(row['Sections']).split(',')
        for sec in sections:
            sec = sec.strip()
            if sec:
                selectable_list.append(f"{abbr}-{sec}")
    return sorted(selectable_list)

def parse_timetable_pdf(pdf_content, course_df):
    """
    Parses the uploaded PDF timetable to extract all class schedules.
    This function is tailored to the specific layout of the provided PDF.
    """
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    all_classes = []
    
    # These coordinates define the columns for time slots.
    # May need adjustment if the PDF format changes.
    # Format: (x_start, x_end, time_slot_label)
    time_slots = [
        (130, 230, "9:30-10:45 am"),
        (250, 350, "11:00 am-12:15 pm"),
        (370, 480, "12:30 - 01:45 pm"),
        (500, 600, "02:30 - 3:45 pm"),
        (620, 720, "4:00-5:15 pm"),
        (740, 840, "5:45-7:00 pm"),
        (860, 960, "7:15-8:30 pm"),
    ]

    # Approximate Y coordinates to distinguish days. This is the most fragile part.
    # We will use the text of the day itself to be more robust.
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    current_day = "Unknown"

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        words = page.get_text("words")  # Get words with their coordinates

        for word in words:
            word_text = word[4]
            x0, y0, x1, y1 = word[0], word[1], word[2], word[3]
            
            # Update the current day when we find a day's name
            for day in days:
                if day.lower() in word_text.lower():
                    current_day = day
                    break
            
            # Check if the word is a class entry using regex
            match = CLASS_PATTERN.search(word_text.replace('\n', ''))
            if match:
                abbr, section, session, faculty, venue = match.groups()
                
                # Find which time slot this class belongs to by its x-coordinate
                time_slot = "Unknown"
                for x_start, x_end, label in time_slots:
                    if x_start < x0 < x_end:
                        time_slot = label
                        break
                
                # Get the full course name from the abbreviation
                course_name_series = course_df[course_df['Abbriviation'] == abbr]['Course Name']
                course_name = course_name_series.iloc[0] if not course_name_series.empty else abbr

                all_classes.append({
                    "Day": current_day,
                    "Time": time_slot,
                    "Course Name": course_name.replace('\n', ' '),
                    "Abbreviation": abbr,
                    "Section": section,
                    "Session": int(session),
                    "Faculty": faculty,
                    "Venue": venue.strip(),
                    "Key": f"{abbr}-{section}" # For filtering
                })

    if not all_classes:
        return pd.DataFrame()

    df = pd.DataFrame(all_classes)
    # Ensure correct day ordering
    day_order = [d for d in days if d in df['Day'].unique()]
    df['Day'] = pd.Categorical(df['Day'], categories=day_order, ordered=True)
    return df.sort_values(by=['Day', 'Time'])


# --- Streamlit App UI ---

st.title("🎓 Personalized Weekly Timetable Generator")
st.write("Select your courses and upload the general weekly schedule PDF to get your personalized timetable.")

# --- Sidebar for User Inputs ---
with st.sidebar:
    st.header("1. Load Course Data")
    course_data_file = st.file_uploader(
        "Upload the 'Course and Sections' CSV file",
        type=['csv'],
        help="This file contains the mapping of course abbreviations to full names and sections."
    )
    
    my_courses = None
    if course_data_file:
        course_df = load_course_data(course_data_file)
        if course_df is not None:
            st.success("Course data loaded successfully!")
            selectable_options = generate_selectable_courses(course_df)
            
            st.header("2. Select Your Courses")
            my_courses = st.multiselect(
                "Choose your course-section pairs:",
                options=selectable_options,
                help="Select all the specific sections you are enrolled in."
            )
    else:
        # Use the file provided by the user as a default
        st.info("Using the default `Course and Sections.csv` file.")
        try:
            course_df = pd.read_csv("Course and Sections.xlsx - Table 2.csv")
            course_df['Abbriviation'] = course_df['Abbriviation'].str.strip()
            selectable_options = generate_selectable_courses(course_df)
            
            st.header("2. Select Your Courses")
            my_courses = st.multiselect(
                "Choose your course-section pairs:",
                options=selectable_options,
                help="Select all the specific sections you are enrolled in."
            )
        except FileNotFoundError:
            st.error("The default `Course and Sections.csv` was not found. Please upload it.")
            course_df = None


# --- Main Panel for PDF Upload and Display ---
st.header("3. Upload General Timetable")
uploaded_pdf = st.file_uploader("Upload the weekly schedule PDF", type="pdf")

if uploaded_pdf and my_courses and course_df is not None:
    with st.spinner("Parsing PDF and generating your schedule..."):
        # Get PDF content
        pdf_content = uploaded_pdf.getvalue()
        
        # Parse the PDF to get a DataFrame of all classes
        schedule_df = parse_timetable_pdf(pdf_content, course_df)

        if not schedule_df.empty:
            # Filter the DataFrame based on user's selected courses
            my_schedule_df = schedule_df[schedule_df['Key'].isin(my_courses)].copy()
            
            st.success("✅ Your personalized timetable is ready!")

            if not my_schedule_df.empty:
                # Display the schedule day by day
                display_cols = ["Time", "Course Name", "Faculty", "Venue", "Session"]
                days_in_schedule = my_schedule_df['Day'].unique()

                for day in days_in_schedule:
                    st.subheader(f"🗓️ {day}")
                    day_df = my_schedule_df[my_schedule_df['Day'] == day][display_cols]
                    st.dataframe(day_df.style.hide(axis="index"), use_container_width=True)
            else:
                st.warning("No classes found for your selected courses in the provided schedule.")
        else:
            st.error("Could not find any class information in the PDF. The PDF format might be different from the expected one.")

elif st.button("Generate My Timetable"):
    if not course_data_file and course_df is None:
        st.error("Please upload the 'Course and Sections' CSV file first.")
    elif not my_courses:
        st.warning("Please select your courses from the sidebar.")
    elif not uploaded_pdf:
        st.warning("Please upload the weekly timetable PDF.")
