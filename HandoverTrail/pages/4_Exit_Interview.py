import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from conflict_detection import get_gap_records
from database import bootstrap
from interviews import (
    add_question,
    delete_question,
    generate_questions,
    get_answers,
    get_questions,
    send_questions,
    submit_answer,
    update_question,
)
from permissions import can_review, normalize_role
from ui import configure_page, empty_state, footer, page_shell, show_flash_toast

configure_page("Exit interview · HandoverTrail")
bootstrap()

PROJECT_ID = "PROJ-DEMO-001"
user_role, _counts = page_shell(
    5,
    "Exit interview",
    "Turn open evidence gaps into questions, then save the departing teammate's answers as reviewable evidence.",
)
show_flash_toast()

if can_review(user_role):
    st.subheader("Prepare questions")
    st.caption(
        "Templates are generated from open gaps. Reviewers can edit or remove drafts, add a question, "
        "and send the remaining drafts to the assigned Departing role."
    )
    if st.button("Generate questions from open gaps", type="primary"):
        created = generate_questions(user_role, PROJECT_ID)
        st.session_state["ui_flash_toast"] = f"Generated {created} new draft question(s)."
        st.rerun()

    gaps = get_gap_records(user_role, PROJECT_ID)
    if gaps:
        with st.expander("Add a question"):
            with st.form("add_interview_question"):
                selected_gap_id = st.selectbox(
                    "Related open gap",
                    [gap["id"] for gap in gaps],
                    format_func=lambda gap_id: next(
                        f"{gap['gap_type'].replace('_', ' ').title()} · "
                        f"{gap['subject'] or gap['id']}"
                        for gap in gaps
                        if gap["id"] == gap_id
                    ),
                )
                custom_question = st.text_area("Question text")
                add_submitted = st.form_submit_button("Add draft question")
            if add_submitted:
                try:
                    add_question(
                        user_role,
                        PROJECT_ID,
                        selected_gap_id,
                        custom_question,
                    )
                except (PermissionError, ValueError) as exc:
                    st.error(f"Could not add question: {exc}")
                else:
                    st.session_state["ui_flash_toast"] = "Draft question added."
                    st.rerun()

    questions = get_questions(user_role, PROJECT_ID)
    drafts = [question for question in questions if question["status"] == "DRAFT"]
    if questions:
        st.markdown("**Draft and sent questions**")
        for question in questions:
            with st.container(border=True):
                st.caption(
                    f"{question['gap_type'].replace('_', ' ').title()} · "
                    f"{question['status'].replace('_', ' ').title()}"
                )
                if question["status"] == "DRAFT":
                    with st.form(f"edit_{question['id']}"):
                        edited_text = st.text_area(
                            "Edit question",
                            value=question["text"],
                            key=f"text_{question['id']}",
                        )
                        save_submitted = st.form_submit_button("Save question")
                    if save_submitted:
                        try:
                            update_question(user_role, question["id"], edited_text)
                        except (PermissionError, ValueError) as exc:
                            st.error(f"Could not update question: {exc}")
                        else:
                            st.session_state["ui_flash_toast"] = "Question updated."
                            st.rerun()
                    if st.button("Delete draft", key=f"delete_{question['id']}"):
                        try:
                            delete_question(user_role, question["id"])
                        except (PermissionError, ValueError) as exc:
                            st.error(f"Could not delete question: {exc}")
                        else:
                            st.session_state["ui_flash_toast"] = "Draft question deleted."
                            st.rerun()
                else:
                    st.write(question["text"])
                    for answer in get_answers(user_role, question["id"]):
                        st.markdown(f"**Answer from {answer['author_name']}**")
                        st.write(answer["text"])
                        st.caption(
                            f"Saved {answer['created_at']} · interview source {answer['source_id']}"
                        )
    else:
        empty_state(
            "There are no draft questions yet.",
            "Generate questions from open gaps or add one to an open gap.",
        )

    if drafts and st.button("Send draft questions to Departing"):
        sent = send_questions(user_role, PROJECT_ID)
        st.session_state["ui_flash_toast"] = f"Sent {sent} question(s) to Departing."
        st.rerun()

elif normalize_role(user_role) == "Departing":
    st.subheader("Questions assigned to you")
    st.caption(
        "Your view contains only questions assigned to the demo Departing identity. "
        "Answers are saved as interview evidence and processed locally into pending claims."
    )
    questions = get_questions(user_role, PROJECT_ID)
    if not questions:
        empty_state("No interview questions have been sent to you yet.")
    for question in questions:
        with st.container(border=True):
            st.caption(question["gap_type"].replace("_", " ").title())
            st.write(question["text"])
            if question["status"] == "ANSWERED":
                st.success("Your answer has been saved for reviewer follow-up.")
                continue
            with st.form(f"answer_{question['id']}"):
                answer_text = st.text_area("Your answer")
                sensitivity = st.selectbox(
                    "Answer visibility",
                    ["restricted", "public"],
                    format_func=str.title,
                    key=f"sensitivity_{question['id']}",
                )
                answer_submitted = st.form_submit_button("Submit answer")
            if answer_submitted:
                try:
                    result = submit_answer(
                        user_role,
                        question["id"],
                        answer_text,
                        sensitivity,
                    )
                except (PermissionError, ValueError, RuntimeError, OSError) as exc:
                    st.error(f"Could not save your answer: {exc}")
                else:
                    if result["claims_created"]:
                        st.session_state["ui_flash_toast"] = (
                            f"Answer saved as interview evidence; "
                            f"{result['claims_created']} pending claim(s) created."
                        )
                    else:
                        st.session_state["ui_flash_toast"] = (
                            "Answer saved as interview evidence. No claim candidate was found; "
                            "the reviewer can inspect the source."
                        )
                    st.rerun()
else:
    st.info("Exit-interview questions are available to Admin, Reviewer, and the assigned Departing role.")

footer()
