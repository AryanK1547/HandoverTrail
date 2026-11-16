import os
import sys

import streamlit as st

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import bootstrap
from handover_plan import build_pickup_plan
from handover_release import (
    acknowledge_latest_release,
    claim_type_priority,
    get_latest_release,
    get_release_readiness,
    release_handover,
    snapshot_markdown,
)
from permissions import can_review, normalize_role
from retrieval import get_claim_evidence, get_visible_claims
from ui import (
    configure_page,
    empty_state,
    footer,
    origin_badge,
    page_navigation,
    page_shell,
    review_badge,
    sensitivity_badge,
    show_flash_toast,
    stat_row,
    step_html,
    trust_badge,
)
from workspace import get_active_project_id

configure_page("Handover · HandoverTrail")
bootstrap()
PROJECT_ID = get_active_project_id()

user_role, _counts = page_shell(
    6,
    "Project handover",
    "Reviewers release a fixed, cited snapshot. Incoming sees the latest released version and records receipt.",
)
show_flash_toast()
query_params = dict(st.query_params)
is_incoming = normalize_role(user_role) == "Incoming"

if not can_review(user_role) and not is_incoming:
    st.info(
        "The handover is released by Admin or Reviewer and read by Incoming. "
        "The Departing role contributes through the exit interview."
    )
    st.page_link(
        "pages/4_Exit_Interview.py",
        label="Open your assigned interview",
        query_params=query_params,
    )
    footer()
    st.stop()

release = get_latest_release(user_role, PROJECT_ID)


def render_pickup_plan(plan: dict) -> None:
    """Ordered first steps and the files to open first, from released claims only."""
    st.markdown("**Where to start**")
    st.caption(
        "Day 1, Week 1, and Month 1 are fixed rules from each claim's type (blockers and "
        "risks first, then queued work, then open questions and dependencies). They are a "
        "reading order, not estimates, and add nothing beyond the released claims."
    )
    if plan["needs_confirmation"]:
        st.warning(
            f"{plan['needs_confirmation']} of {plan['total']} claim(s) rest on one source or "
            "have conflicting sources. Confirm those with the people involved before acting."
        )
    if not plan["steps"]:
        st.info("This release has no next actions, blockers, risks, or owners to start from.")
    number = 0
    for horizon in plan["horizons"]:
        st.markdown(f"**{horizon['name']}** · {horizon['guidance']}")
        for step in horizon["steps"]:
            number += 1
            detail = f"{step['why']} Source: {step['source']}."
            if step["confirm"]:
                detail += f" {step['confirm']}"
            st.markdown(
                step_html(number, step["verb"], step["text"], detail),
                unsafe_allow_html=True,
            )
    if plan["focus_sources"]:
        st.markdown("**Where to work: open these sources first**")
        for name, count in plan["focus_sources"]:
            st.markdown(f"- {name} · supports {count} released claim(s)")


@st.dialog("Confirm handover release")
def confirm_release(summary: dict) -> None:
    next_version = summary["latest_version"] + 1
    st.write(
        f"Release version {next_version} to the Incoming role? A released snapshot "
        "is fixed and cannot be edited or deleted."
    )
    st.markdown(
        f"- **{summary['releasable']}** approved claim(s) with public evidence will be included.\n"
        f"- **{summary['approved_excluded']}** approved claim(s) are excluded because they "
        "rely on restricted sources or have no evidence.\n"
        f"- **{summary['pending']}** claim(s) are still awaiting review and are not included.\n"
        f"- **{summary['unresolved_conflicts']}** conflict(s) are unresolved and "
        f"**{summary['open_gaps']}** evidence gap(s) are open."
    )
    confirm_column, cancel_column = st.columns(2)
    with confirm_column:
        if st.button("Confirm release", type="primary"):
            try:
                created_release = release_handover(user_role, PROJECT_ID)
            except (PermissionError, ValueError) as exc:
                st.error(f"The handover was not released: {exc}")
            else:
                st.session_state["ui_flash_toast"] = (
                    f"Handover version {created_release['version']} released."
                )
                st.rerun()
    with cancel_column:
        if st.button("Cancel"):
            st.rerun()


if can_review(user_role):
    readiness = get_release_readiness(user_role, PROJECT_ID)
    with st.container(border=True):
        st.subheader("Handover release")
        if release:
            st.success(
                f"Latest release: version {release['version']} · {release['released_at']} · "
                f"{len(release['snapshot']['claims'])} approved claim(s)."
            )
            if release["acknowledgements"]:
                for acknowledgement in release["acknowledgements"]:
                    st.info(
                        f"Acknowledged by {acknowledgement['user_name']} at "
                        f"{acknowledgement['acknowledged_at']}."
                    )
            else:
                st.caption(
                    "Incoming has not acknowledged this version. Switch the demo role to "
                    "Incoming in the sidebar to view and acknowledge it."
                )
            st.download_button(
                f"Download version {release['version']} as Markdown",
                data=snapshot_markdown(release),
                file_name=f"handover_v{release['version']}.md",
                mime="text/markdown",
            )
        else:
            st.caption("No release exists yet. Incoming cannot see live handover content.")

        st.markdown("**What the next release would contain**")
        stat_row(
            [
                ("Included claims", readiness["releasable"]),
                ("Approved but excluded", readiness["approved_excluded"]),
                ("Awaiting review", readiness["pending"]),
                ("Unresolved conflicts", readiness["unresolved_conflicts"]),
                ("Open gaps", readiness["open_gaps"]),
            ]
        )
        st.caption(
            "Only approved claims whose evidence is entirely public are released. "
            "Recipient: the Incoming role."
        )
        if not readiness["releasable"]:
            release_blocker = (
                "Nothing can be released yet: approve at least one claim supported only "
                "by public sources."
            )
        elif not readiness["has_unreleased_changes"]:
            release_blocker = (
                f"Version {readiness['latest_version']} already contains the current "
                "approved claims. Approve, edit, or reject a claim to prepare a new version."
            )
        else:
            release_blocker = None
        if release_blocker:
            st.info(release_blocker)
            if readiness["pending"]:
                st.page_link(
                    "pages/2_Review_Claims.py",
                    label=f"Review {readiness['pending']} pending claim(s) →",
                    query_params=query_params,
                )
        elif readiness["pending"] or readiness["unresolved_conflicts"]:
            st.warning(
                "You can release now, but pending claims are left out and unresolved "
                "conflicts are not flagged to Incoming beyond each claim's trust label."
            )
        if st.button(
            "Release current approved handover",
            type="primary",
            disabled=release_blocker is not None,
        ):
            confirm_release(readiness)

    if readiness["releasable_claims"]:
        with st.expander("Preview the start plan Incoming will see"):
            render_pickup_plan(build_pickup_plan(readiness["releasable_claims"]))
    releasable_ids = readiness["releasable_claim_ids"]
    claims_for_display = [
        dict(claim)
        for claim in get_visible_claims(user_role, PROJECT_ID)
        if claim["review_status"] == "APPROVED"
    ]
    st.subheader("Approved claims (live preview)")
    st.caption(
        "These are the currently approved claims, not the fixed snapshot Incoming reads. "
        "Claims marked as not releasable stay visible to Admin and Reviewer only."
    )
else:
    releasable_ids = None
    if not release:
        empty_state(
            "No handover has been released yet.",
            "A Reviewer or Admin must release an approved snapshot before it appears here.",
        )
        footer()
        st.stop()
    st.subheader(f"Released handover · Version {release['version']}")
    st.info(
        "This is the latest fixed snapshot a Reviewer approved for release. "
        "Unreleased candidate claims and later edits are not shown here."
    )
    st.caption(
        f"Released {release['released_at']}. This is a fixed snapshot; later claim edits "
        "appear only in a newer release."
    )
    acknowledgement = next(
        (
            item
            for item in release["acknowledgements"]
            if item["user_id"] == "USR-DEMO-INCOMING"
        ),
        None,
    )
    if acknowledgement:
        st.success(
            f"You acknowledged version {release['version']} at "
            f"{acknowledgement['acknowledged_at']}."
        )
    elif st.button(
        f"Acknowledge receipt of version {release['version']}",
        type="primary",
    ):
        try:
            acknowledge_latest_release(user_role, PROJECT_ID)
        except (PermissionError, ValueError) as exc:
            st.error(f"Could not save acknowledgement: {exc}")
        else:
            st.session_state["ui_flash_toast"] = (
                f"Receipt of handover version {release['version']} recorded."
            )
            st.rerun()
    claims_for_display = release["snapshot"]["claims"]

    type_counts: dict[str, int] = {}
    for claim in claims_for_display:
        type_counts[claim["claim_type"]] = type_counts.get(claim["claim_type"], 0) + 1
    with st.container(border=True):
        st.subheader("Where to pick up")
        st.write(
            " · ".join(
                f"{count} {claim_type}"
                for claim_type, count in sorted(
                    type_counts.items(), key=lambda item: claim_type_priority(item[0])
                )
            )
        )
        render_pickup_plan(build_pickup_plan(claims_for_display))
        st.caption(
            "Every claim below cites the source excerpt a reviewer checked; open it "
            "before relying on the claim."
        )
        st.download_button(
            f"Download version {release['version']} as Markdown",
            data=snapshot_markdown(release),
            file_name=f"handover_v{release['version']}.md",
            mime="text/markdown",
        )

if not claims_for_display:
    empty_state(
        "No approved claims are available for this handover.",
        "Approve claims supported only by public sources, then release a new version.",
    )
    if can_review(user_role):
        st.page_link(
            "pages/2_Review_Claims.py",
            label="Review claims →",
            query_params=query_params,
        )
else:
    claims_for_display = sorted(
        claims_for_display,
        key=lambda claim: claim_type_priority(claim["claim_type"]),
    )
    claim_types = sorted({claim["claim_type"] for claim in claims_for_display})
    filter_columns = st.columns(2)
    with filter_columns[0]:
        selected_type = st.selectbox("Claim type", ["All types", *claim_types])
    with filter_columns[1]:
        claim_search = st.text_input("Search released claims", placeholder="Type a keyword")
    filtered_claims = claims_for_display
    if selected_type != "All types":
        filtered_claims = [
            claim for claim in filtered_claims if claim["claim_type"] == selected_type
        ]
    if claim_search.strip():
        query = claim_search.casefold().strip()
        filtered_claims = [
            claim
            for claim in filtered_claims
            if query in claim["claim_text"].casefold()
            or query in claim["claim_type"].casefold()
        ]
    page_size = st.selectbox("Claims per page", [10, 25, 50], index=0)
    page_count = max(1, (len(filtered_claims) + page_size - 1) // page_size)
    page_signature = (
        selected_type,
        claim_search.casefold(),
        page_size,
        len(filtered_claims),
    )
    signature_key = f"handover_filter_signature_{PROJECT_ID}"
    page_key = f"handover_page_number_{PROJECT_ID}"
    if st.session_state.get(signature_key) != page_signature:
        st.session_state[signature_key] = page_signature
        st.session_state[page_key] = 1
    page_number = st.selectbox(
        "Handover page",
        range(1, page_count + 1),
        key=page_key,
    )
    start = (page_number - 1) * page_size
    if not filtered_claims:
        empty_state("No released claims match these filters.")
    else:
        st.caption(
            f"Showing claims {start + 1}–{min(start + page_size, len(filtered_claims))} "
            f"of {len(filtered_claims)}."
        )
    for claim in filtered_claims[start : start + page_size]:
        with st.container(border=True):
            st.caption(claim["claim_type"])
            st.markdown(
                f"{trust_badge(claim['trust_status'])} "
                f"{review_badge(claim['review_status'])} "
                f"{origin_badge(claim['claim_source'])}",
                unsafe_allow_html=True,
            )
            st.markdown(claim["claim_text"])
            if releasable_ids is not None and claim["claim_id"] not in releasable_ids:
                st.caption(
                    "Not releasable to Incoming: this claim relies on a restricted source "
                    "or has no readable evidence."
                )
            with st.expander("Source evidence"):
                evidence_list = (
                    claim["evidence"]
                    if is_incoming
                    else get_claim_evidence(user_role, claim["claim_id"])
                )
                if not evidence_list:
                    empty_state("No readable source evidence is available for this claim.")
                for evidence in evidence_list:
                    st.markdown(f"**{evidence['file_name']}**")
                    st.markdown(
                        sensitivity_badge(evidence["sensitivity"]),
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        evidence["reference_location"] or "Source location unavailable"
                    )
                    st.write(evidence["excerpt"])

page_navigation(
    previous=("Review claims", "pages/2_Review_Claims.py") if can_review(user_role) else None,
    following=(("Exit interview", "pages/4_Exit_Interview.py"),) if can_review(user_role) else (),
)
footer()
