import os
import hashlib
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from supabase_database import (
    add_client,
    get_clients,
    get_client,
    update_client,
    delete_client,
    add_candidate,
    get_candidates,
    get_candidate,
    update_candidate,
    delete_candidate,
    save_screening_result,
    save_interview_script,
    save_evaluation,
    count_records,
    run_safe_admin_command
)

from resume_parser import extract_resume_text
from ai_engine import ask_ai, generate_ai_response

from prompts import (
    client_formatter_prompt,
    screening_prompt,
    interview_script_prompt,
    evaluation_prompt
)


load_dotenv()


st.set_page_config(
    page_title="AI Hiring Engine",
    layout="wide"
)


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def client_duplicate_exists(client_name, location):
    existing_clients = get_clients()

    new_name = normalize_text(client_name)
    new_location = normalize_text(location)

    for client in existing_clients:
        existing_name = normalize_text(client[1])
        existing_location = normalize_text(client[3])

        if existing_name == new_name and existing_location == new_location:
            return True

    return False


def admin_login():
    st.subheader("Administrator Login")

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == admin_username and hash_password(password) == admin_password_hash:
            st.session_state.admin_logged_in = True
            st.success("Admin login successful.")
            st.rerun()
        else:
            st.error("Invalid admin username or password.")


def require_admin():
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        admin_login()
        st.stop()


# -----------------------------
# APP TITLE AND MENU
# -----------------------------

st.title("AI Hiring Engine")


menu = st.sidebar.selectbox(
    "Menu",
    [
        "Dashboard",
        "Add Client",
        "Add Candidate",
        "Run Screening",
        "Generate Interview Script",
        "Evaluate Candidate",
        "Search Candidates",
        "Administrator"
    ]
)


# -----------------------------
# DASHBOARD
# -----------------------------

if menu == "Dashboard":
    st.header("Dashboard")

    candidates = get_candidates()
    clients = get_clients()

    col1, col2 = st.columns(2)

    col1.metric("Total Candidates", len(candidates))
    col2.metric("Total Clients", len(clients))

    st.info(
        "Use the sidebar to add clients, add candidates, run screening, generate scripts, "
        "evaluate interviews, search candidates, or open Administrator."
    )


# -----------------------------
# ADD CLIENT
# -----------------------------

if menu == "Add Client":
    st.header("Add Client")

    add_client_tabs = st.tabs([
        "Single Client",
        "Mass Import CSV"
    ])

    with add_client_tabs[0]:
        st.subheader("Single Client Add")

        st.write(
            "Enter the client name, location, and fragmented client needs. "
            "Click Format Client Needs to let Qwen clean and structure the client profile."
        )

        client_name = st.text_input(
            "Client Name",
            placeholder="Example: Huntsville Photographer Client",
            key="single_client_name"
        )

        location = st.text_input(
            "Location / Geo Location",
            placeholder="Example: Huntsville, AL or Las Vegas, NV",
            key="single_client_location"
        )

        client_needs = st.text_area(
            "Client Needs",
            height=350,
            placeholder="""
Paste fragmented client needs here.

Example:
Huntsville photographer
part time
$25/unit, $30 once drone licensed
training $15/hr
needs weekday coverage
twilight availability
drone license required before hired
client wants someone green, coachable, fun, energetic
not someone with their own real estate media business
must have reliable car
coverage about 1 hour around Huntsville
Tuesday Thursday important
""",
            key="single_client_needs"
        )

        if "formatted_client_needs" not in st.session_state:
            st.session_state.formatted_client_needs = ""

        if st.button("Format Client Needs", key="format_single_client"):
            if not client_needs.strip():
                st.error("Please paste the client needs first.")
            else:
                raw_notes_with_context = f"""
Client Name:
{client_name if client_name else "Not specified"}

Location:
{location if location else "Not specified"}

Fragmented Client Needs:
{client_needs}
"""

                prompt = client_formatter_prompt(raw_notes_with_context)
                formatted_details = ask_ai(prompt)

                st.session_state.formatted_client_needs = formatted_details

                st.success("Client needs formatted.")

        formatted_client_needs = st.text_area(
            "Formatted Client Needs",
            value=st.session_state.formatted_client_needs,
            height=500,
            key="single_formatted_client_needs"
        )

        if st.button("Submit Client", key="submit_single_client"):
            if not client_name.strip():
                st.error("Please enter the client name.")
            elif not location.strip():
                st.error("Please enter the location / geo location.")
            elif not formatted_client_needs.strip():
                st.error("Please format the client needs before submitting.")
            elif client_duplicate_exists(client_name, location):
                st.warning("Duplicate client found. This client was not uploaded.")
            else:
                add_client(
                    client_name,
                    "Not specified",
                    location,
                    formatted_client_needs,
                    formatted_client_needs,
                    formatted_client_needs,
                    formatted_client_needs,
                    formatted_client_needs,
                    formatted_client_needs
                )

                st.success("Client submitted successfully.")
                st.session_state.formatted_client_needs = ""

    with add_client_tabs[1]:
        st.subheader("Mass Import Clients from CSV")

        st.write(
            "Upload a CSV with your client intake columns. "
            "Each row will be converted into client notes, formatted by Qwen, then saved as a client."
        )

        st.warning(
            "Large imports can take time because Qwen formats each row one by one. "
            "For testing, you can import a smaller batch first."
        )

        uploaded_csv = st.file_uploader(
            "Upload Client CSV",
            type=["csv"],
            key="client_csv_upload"
        )

        expected_headers = [
            "Name",
            "Company Name",
            "What is your email address?",
            "monday Doc",
            "What Role Are You Hiring?",
            "Request Date",
            "Due by Date",
            "What would be the ideal location for the hire?",
            "Compensation Type",
            "Compensation Details",
            "Is Gear Provided by The Company?",
            "Employment Type",
            "How Many Hours Per Week Will This Employee Work?",
            "Any Specific Availability Requirements?",
            "What kind of character traits or values do you believe are essential for someone to thrive on your team?",
            "Anything else we should know?",
            "Hiring Radius",
            "Green or Experienced?",
            "Service Radius",
            "Urgency"
        ]

        def safe_value(row, column_name):
            if column_name not in row:
                return ""
            value = row[column_name]
            if pd.isna(value):
                return ""
            return str(value).strip()

        def build_client_notes_from_row(row):
            name = safe_value(row, "Name")
            company_name = safe_value(row, "Company Name")
            email = safe_value(row, "What is your email address?")
            monday_doc = safe_value(row, "monday Doc")
            role = safe_value(row, "What Role Are You Hiring?")
            request_date = safe_value(row, "Request Date")
            due_by_date = safe_value(row, "Due by Date")
            ideal_location = safe_value(row, "What would be the ideal location for the hire?")
            compensation_type = safe_value(row, "Compensation Type")
            compensation_details = safe_value(row, "Compensation Details")
            gear_provided = safe_value(row, "Is Gear Provided by The Company?")
            employment_type = safe_value(row, "Employment Type")
            hours_per_week = safe_value(row, "How Many Hours Per Week Will This Employee Work?")
            availability_requirements = safe_value(row, "Any Specific Availability Requirements?")
            character_traits = safe_value(row, "What kind of character traits or values do you believe are essential for someone to thrive on your team?")
            anything_else = safe_value(row, "Anything else we should know?")
            hiring_radius = safe_value(row, "Hiring Radius")
            green_or_experienced = safe_value(row, "Green or Experienced?")
            service_radius = safe_value(row, "Service Radius")
            urgency = safe_value(row, "Urgency")

            client_display_name = company_name or name or "Unnamed Client"
            client_location = ideal_location or "Not specified"

            raw_notes = f"""
Client Name:
{client_display_name}

Contact Name:
{name if name else "Not specified"}

Company Name:
{company_name if company_name else "Not specified"}

Email:
{email if email else "Not specified"}

Monday Doc:
{monday_doc if monday_doc else "Not specified"}

Role Hiring:
{role if role else "Not specified"}

Request Date:
{request_date if request_date else "Not specified"}

Due By Date:
{due_by_date if due_by_date else "Not specified"}

Ideal Location for Hire:
{ideal_location if ideal_location else "Not specified"}

Compensation Type:
{compensation_type if compensation_type else "Not specified"}

Compensation Details:
{compensation_details if compensation_details else "Not specified"}

Is Gear Provided by the Company:
{gear_provided if gear_provided else "Not specified"}

Employment Type:
{employment_type if employment_type else "Not specified"}

Hours Per Week:
{hours_per_week if hours_per_week else "Not specified"}

Specific Availability Requirements:
{availability_requirements if availability_requirements else "Not specified"}

Essential Character Traits / Values:
{character_traits if character_traits else "Not specified"}

Anything Else We Should Know:
{anything_else if anything_else else "Not specified"}

Hiring Radius:
{hiring_radius if hiring_radius else "Not specified"}

Green or Experienced:
{green_or_experienced if green_or_experienced else "Not specified"}

Service Radius:
{service_radius if service_radius else "Not specified"}

Urgency:
{urgency if urgency else "Not specified"}
"""

            return client_display_name, client_location, role, raw_notes

        if uploaded_csv:
            try:
                df = pd.read_csv(uploaded_csv)
            except UnicodeDecodeError:
                uploaded_csv.seek(0)
                df = pd.read_csv(uploaded_csv, encoding="latin-1")

            st.subheader("CSV Preview")
            st.write(f"Total rows found: {len(df)}")

            st.dataframe(
                df,
                use_container_width=True,
                height=700
            )

            missing_headers = [
                header for header in expected_headers
                if header not in df.columns
            ]

            if missing_headers:
                st.warning("Some expected headers are missing from this CSV:")
                st.write(missing_headers)
                st.info(
                    "The import can still run, but missing fields will be marked as Not specified."
                )
            else:
                st.success("All expected headers found.")

            max_rows = st.number_input(
                "How many rows do you want to import?",
                min_value=1,
                max_value=len(df),
                value=len(df),
                step=1
            )

            start_row = st.number_input(
                "Start from row number",
                min_value=1,
                max_value=len(df),
                value=1,
                step=1
            )

            end_row = min(int(start_row) + int(max_rows) - 1, len(df))

            st.write(
                f"Ready to import rows {start_row} to {end_row}."
            )

            if st.button("Import Clients from CSV", key="import_clients_csv"):
                imported_count = 0
                skipped_duplicates = []
                failed_rows = []

                progress_bar = st.progress(0)
                status_box = st.empty()

                start_index = int(start_row) - 1
                end_index = min(start_index + int(max_rows), len(df))
                import_df = df.iloc[start_index:end_index]

                existing_clients = get_clients()
                existing_client_keys = set()

                for existing_client in existing_clients:
                    existing_name = normalize_text(existing_client[1])
                    existing_location = normalize_text(existing_client[3])
                    existing_client_keys.add((existing_name, existing_location))

                for processed_number, (index, row) in enumerate(import_df.iterrows(), start=1):
                    try:
                        client_display_name, client_location, role, raw_notes = build_client_notes_from_row(row)

                        client_key = (
                            normalize_text(client_display_name),
                            normalize_text(client_location)
                        )

                        if client_key in existing_client_keys:
                            skipped_duplicates.append({
                                "row": index + 1,
                                "client": client_display_name,
                                "location": client_location,
                                "reason": "Duplicate client name and location"
                            })

                            status_box.write(
                                f"Skipped duplicate row {index + 1}: {client_display_name}"
                            )

                        else:
                            status_box.write(
                                f"Formatting and importing row {index + 1}: {client_display_name}"
                            )

                            prompt = client_formatter_prompt(raw_notes)
                            formatted_details = ask_ai(prompt)

                            add_client(
                                client_display_name,
                                role if role else "Not specified",
                                client_location,
                                formatted_details,
                                formatted_details,
                                formatted_details,
                                formatted_details,
                                formatted_details,
                                formatted_details
                            )

                            existing_client_keys.add(client_key)
                            imported_count += 1

                    except Exception as error:
                        failed_rows.append({
                            "row": index + 1,
                            "error": str(error)
                        })

                    progress_value = processed_number / max(1, len(import_df))
                    progress_bar.progress(min(progress_value, 1.0))

                st.success(f"Import complete. Imported {imported_count} clients.")

                if skipped_duplicates:
                    st.warning(f"Skipped {len(skipped_duplicates)} duplicate clients.")
                    st.write(skipped_duplicates)

                if failed_rows:
                    st.error(f"{len(failed_rows)} rows failed.")
                    st.write(failed_rows)


# -----------------------------
# ADD CANDIDATE
# -----------------------------

if menu == "Add Candidate":
    st.header("Add Candidate")

    candidate_name = st.text_input("Candidate Name")
    location = st.text_input("Candidate Location")
    applied_role = st.text_input("Applied Role")
    screening_answers = st.text_area("Screening Questions and Answers", height=250)
    portfolio_links = st.text_area("Portfolio Links")

    resume_file = st.file_uploader(
        "Upload Resume",
        type=["pdf", "docx", "txt"]
    )

    if st.button("Save Candidate"):
        if not candidate_name.strip():
            st.error("Please enter the candidate name.")
        elif not location.strip():
            st.error("Please enter the candidate location.")
        elif not applied_role.strip():
            st.error("Please enter the applied role.")
        else:
            resume_text = ""

            if resume_file:
                os.makedirs("uploads", exist_ok=True)

                file_path = os.path.join("uploads", resume_file.name)

                with open(file_path, "wb") as file:
                    file.write(resume_file.getbuffer())

                file_type = resume_file.name.split(".")[-1].lower()
                resume_text = extract_resume_text(file_path, file_type)

            candidate_id = add_candidate(
                candidate_name,
                location,
                applied_role,
                resume_text,
                screening_answers,
                portfolio_links
            )

            st.success(f"Candidate saved. Candidate ID: {candidate_id}")


# -----------------------------
# RUN SCREENING
# -----------------------------

if menu == "Run Screening":
    st.header("Run Screening")

    candidates = get_candidates()
    clients = get_clients()

    if not candidates:
        st.warning("No candidates found. Add a candidate first.")
    elif not clients:
        st.warning("No clients found. Add a client first.")
    else:
        candidate_options = {
            f"{candidate[1]} | {candidate[3]} | ID {candidate[0]}": candidate[0]
            for candidate in candidates
        }

        client_options = {
            f"{client[1]} | {client[2]} | {client[3]} | ID {client[0]}": client[0]
            for client in clients
        }

        selected_candidate = st.selectbox(
            "Select Candidate",
            list(candidate_options.keys()),
            key="screening_candidate"
        )

        selected_client = st.selectbox(
            "Select Client",
            list(client_options.keys()),
            key="screening_client"
        )

        if st.button("Run AI Screening"):
            candidate_id = candidate_options[selected_candidate]
            client_id = client_options[selected_client]

            candidate = get_candidate(candidate_id)
            client = get_client(client_id)

            prompt = screening_prompt(candidate, client)
            result = ask_ai(prompt)

            save_screening_result(candidate_id, client_id, result)

            st.subheader("Screening Result")
            st.write(result)


# -----------------------------
# GENERATE INTERVIEW SCRIPT
# -----------------------------

if menu == "Generate Interview Script":
    st.header("Generate Interview Script")

    candidates = get_candidates()
    clients = get_clients()

    if not candidates:
        st.warning("No candidates found. Add a candidate first.")
    elif not clients:
        st.warning("No clients found. Add a client first.")
    else:
        candidate_options = {
            f"{candidate[1]} | {candidate[3]} | ID {candidate[0]}": candidate[0]
            for candidate in candidates
        }

        client_options = {
            f"{client[1]} | {client[2]} | {client[3]} | ID {client[0]}": client[0]
            for client in clients
        }

        selected_candidate = st.selectbox(
            "Select Candidate",
            list(candidate_options.keys()),
            key="script_candidate"
        )

        selected_client = st.selectbox(
            "Select Client",
            list(client_options.keys()),
            key="script_client"
        )

        if st.button("Generate Script"):
            candidate_id = candidate_options[selected_candidate]
            client_id = client_options[selected_client]

            candidate = get_candidate(candidate_id)
            client = get_client(client_id)

            prompt = interview_script_prompt(candidate, client)
            script = ask_ai(prompt)

            save_interview_script(candidate_id, client_id, script)

            st.subheader("Interview Script")
            st.write(script)


# -----------------------------
# EVALUATE CANDIDATE
# -----------------------------

if menu == "Evaluate Candidate":
    st.header("Evaluate Candidate")

    candidates = get_candidates()
    clients = get_clients()

    if not candidates:
        st.warning("No candidates found. Add a candidate first.")
    elif not clients:
        st.warning("No clients found. Add a client first.")
    else:
        candidate_options = {
            f"{candidate[1]} | {candidate[3]} | ID {candidate[0]}": candidate[0]
            for candidate in candidates
        }

        client_options = {
            f"{client[1]} | {client[2]} | {client[3]} | ID {client[0]}": client[0]
            for client in clients
        }

        selected_candidate = st.selectbox(
            "Select Candidate",
            list(candidate_options.keys()),
            key="evaluation_candidate"
        )

        selected_client = st.selectbox(
            "Select Client",
            list(client_options.keys()),
            key="evaluation_client"
        )

        transcript = st.text_area("Paste Interview Transcript", height=350)

        if st.button("Evaluate Interview"):
            if not transcript.strip():
                st.error("Please paste the interview transcript first.")
            else:
                candidate_id = candidate_options[selected_candidate]
                client_id = client_options[selected_client]

                candidate = get_candidate(candidate_id)
                client = get_client(client_id)

                prompt = evaluation_prompt(candidate, client, transcript)
                evaluation = ask_ai(prompt)

                save_evaluation(candidate_id, client_id, transcript, evaluation)

                st.subheader("Evaluation")
                st.write(evaluation)


# -----------------------------
# SEARCH CANDIDATES
# -----------------------------

if menu == "Search Candidates":
    st.header("Search Candidates")

    search = st.text_input("Search candidate name")

    candidates = get_candidates()

    if not candidates:
        st.warning("No candidates found.")
    else:
        for candidate in candidates:
            candidate_id = candidate[0]
            name = candidate[1] or ""
            candidate_location = candidate[2] or ""
            role = candidate[3] or ""

            if search.lower() in name.lower():
                st.markdown(f"### {name}")
                st.write(f"Location: {candidate_location}")
                st.write(f"Applied Role: {role}")
                st.write(f"Candidate ID: {candidate_id}")
                st.divider()


# -----------------------------
# ADMINISTRATOR
# -----------------------------

if menu == "Administrator":
    st.header("Administrator Panel")

    require_admin()

    st.success("Administrator access granted.")

    if st.button("Logout Admin"):
        st.session_state.admin_logged_in = False
        st.rerun()

    admin_tabs = st.tabs([
        "Overview",
        "Manage Clients",
        "Manage Candidates",
        "Command Console"
    ])

    with admin_tabs[0]:
        st.subheader("Admin Overview")

        counts = count_records()

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Clients", counts.get("clients", 0))
        col2.metric("Candidates", counts.get("candidates", 0))
        col3.metric("Screenings", counts.get("screening_results", 0))
        col4.metric("Scripts", counts.get("interview_scripts", 0))
        col5.metric("Evaluations", counts.get("evaluations", 0))

        st.info("Use this panel to override, fix, edit, delete, and maintain records.")

    with admin_tabs[1]:
        st.subheader("Manage Clients")

        clients = get_clients()

        if not clients:
            st.warning("No clients found.")
        else:
            st.write("Click a client name to view or edit their formatted needs.")

            client_search = st.text_input(
                "Search Clients",
                key="admin_client_search"
            )

            filtered_clients = []

            for client in clients:
                client_id = client[0]
                client_name = client[1] or ""
                client_role = client[2] or ""
                client_location = client[3] or ""

                search_text = f"{client_name} {client_role} {client_location}".lower()

                if client_search.lower() in search_text:
                    filtered_clients.append(client)

            col_list, col_detail = st.columns([1, 2])

            with col_list:
                st.markdown("### Client List")

                for client in filtered_clients:
                    client_id = client[0]
                    client_name = client[1] or "Unnamed Client"
                    client_location = client[3] or "No location"

                    button_label = f"{client_name} | {client_location}"

                    if st.button(button_label, key=f"client_select_{client_id}"):
                        st.session_state.selected_admin_client_id = client_id

            with col_detail:
                st.markdown("### Client Details")

                if "selected_admin_client_id" not in st.session_state:
                    st.info("Select a client from the list.")
                else:
                    selected_client_id = st.session_state.selected_admin_client_id
                    client = get_client(selected_client_id)

                    if not client:
                        st.error("Client not found.")
                    else:
                        st.write(f"Editing Client ID: {selected_client_id}")

                        edit_client_name = st.text_input(
                            "Client Name",
                            value=client[1] or "",
                            key=f"edit_client_name_{selected_client_id}"
                        )

                        edit_client_location = st.text_input(
                            "Location / Geo Location",
                            value=client[3] or "",
                            key=f"edit_client_location_{selected_client_id}"
                        )

                        formatted_needs_value = client[9] or client[4] or ""

                        edit_formatted_needs = st.text_area(
                            "Formatted Client Needs",
                            value=formatted_needs_value,
                            height=600,
                            key=f"edit_client_needs_{selected_client_id}"
                        )

                        col_save, col_delete = st.columns(2)

                        with col_save:
                            if st.button("Save Client Changes", key=f"save_client_{selected_client_id}"):
                                update_client(
                                    selected_client_id,
                                    edit_client_name,
                                    "Not specified",
                                    edit_client_location,
                                    edit_formatted_needs,
                                    edit_formatted_needs,
                                    edit_formatted_needs,
                                    edit_formatted_needs,
                                    edit_formatted_needs,
                                    edit_formatted_needs
                                )

                                st.success("Client updated.")
                                st.rerun()

                        with col_delete:
                            confirm_delete_client = st.checkbox(
                                "Confirm delete this client and related records.",
                                key=f"confirm_delete_client_{selected_client_id}"
                            )

                            if st.button("Delete Client", key=f"delete_client_{selected_client_id}"):
                                if confirm_delete_client:
                                    delete_client(selected_client_id)

                                    if "selected_admin_client_id" in st.session_state:
                                        del st.session_state.selected_admin_client_id

                                    st.success("Client deleted.")
                                    st.rerun()
                                else:
                                    st.error("Please confirm before deleting.")

    with admin_tabs[2]:
        st.subheader("Manage Candidates")

        candidates = get_candidates()

        if not candidates:
            st.warning("No candidates found.")
        else:
            st.write("Click a candidate name to view or edit their information.")

            candidate_search = st.text_input(
                "Search Candidates",
                key="admin_candidate_search"
            )

            filtered_candidates = []

            for candidate in candidates:
                candidate_id = candidate[0]
                candidate_name = candidate[1] or ""
                candidate_location = candidate[2] or ""
                applied_role = candidate[3] or ""

                search_text = f"{candidate_name} {candidate_location} {applied_role}".lower()

                if candidate_search.lower() in search_text:
                    filtered_candidates.append(candidate)

            col_list, col_detail = st.columns([1, 2])

            with col_list:
                st.markdown("### Candidate List")

                for candidate in filtered_candidates:
                    candidate_id = candidate[0]
                    candidate_name = candidate[1] or "Unnamed Candidate"
                    applied_role = candidate[3] or "No role"

                    button_label = f"{candidate_name} | {applied_role}"

                    if st.button(button_label, key=f"candidate_select_{candidate_id}"):
                        st.session_state.selected_admin_candidate_id = candidate_id

            with col_detail:
                st.markdown("### Candidate Details")

                if "selected_admin_candidate_id" not in st.session_state:
                    st.info("Select a candidate from the list.")
                else:
                    selected_candidate_id = st.session_state.selected_admin_candidate_id
                    candidate = get_candidate(selected_candidate_id)

                    if not candidate:
                        st.error("Candidate not found.")
                    else:
                        st.write(f"Editing Candidate ID: {selected_candidate_id}")

                        edit_candidate_name = st.text_input(
                            "Candidate Name",
                            value=candidate[1] or "",
                            key=f"edit_candidate_name_{selected_candidate_id}"
                        )

                        edit_candidate_location = st.text_input(
                            "Candidate Location",
                            value=candidate[2] or "",
                            key=f"edit_candidate_location_{selected_candidate_id}"
                        )

                        edit_applied_role = st.text_input(
                            "Applied Role",
                            value=candidate[3] or "",
                            key=f"edit_candidate_role_{selected_candidate_id}"
                        )

                        edit_resume_text = st.text_area(
                            "Resume Text",
                            value=candidate[4] or "",
                            height=300,
                            key=f"edit_candidate_resume_{selected_candidate_id}"
                        )

                        edit_screening_answers = st.text_area(
                            "Screening Answers",
                            value=candidate[5] or "",
                            height=300,
                            key=f"edit_candidate_screening_{selected_candidate_id}"
                        )

                        edit_portfolio_links = st.text_area(
                            "Portfolio Links",
                            value=candidate[6] or "",
                            height=150,
                            key=f"edit_candidate_portfolio_{selected_candidate_id}"
                        )

                        col_save, col_delete = st.columns(2)

                        with col_save:
                            if st.button("Save Candidate Changes", key=f"save_candidate_{selected_candidate_id}"):
                                update_candidate(
                                    selected_candidate_id,
                                    edit_candidate_name,
                                    edit_candidate_location,
                                    edit_applied_role,
                                    edit_resume_text,
                                    edit_screening_answers,
                                    edit_portfolio_links
                                )

                                st.success("Candidate updated.")
                                st.rerun()

                        with col_delete:
                            confirm_delete_candidate = st.checkbox(
                                "Confirm delete this candidate and related records.",
                                key=f"confirm_delete_candidate_{selected_candidate_id}"
                            )

                            if st.button("Delete Candidate", key=f"delete_candidate_{selected_candidate_id}"):
                                if confirm_delete_candidate:
                                    delete_candidate(selected_candidate_id)

                                    if "selected_admin_candidate_id" in st.session_state:
                                        del st.session_state.selected_admin_candidate_id

                                    st.success("Candidate deleted.")
                                    st.rerun()
                                else:
                                    st.error("Please confirm before deleting.")

    with admin_tabs[3]:
        st.subheader("Admin Command Console")

        st.warning(
            "This is a safe admin console, not a full system terminal. "
            "It only allows approved maintenance commands."
        )

        st.write("Available commands:")

        st.code("""
show counts
show tables
list clients
list candidates
delete client 1
delete candidate 1
find client huntsville
find candidate john
""")

        admin_command = st.text_input("Enter admin command", key="admin_command")

        if st.button("Run Command", key="run_admin_command"):
            if not admin_command.strip():
                st.error("Please enter a command.")
            else:
                result = run_safe_admin_command(admin_command)

                st.subheader("Command Result")
                st.write(result)