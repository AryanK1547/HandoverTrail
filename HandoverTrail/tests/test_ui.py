import re

from ui import COLORS, TEXT_BACKGROUND_PAIRS, badge_html, role_badge, sensitivity_badge


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground: str, background: str) -> float:
    luminance = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (luminance[0] + 0.05) / (luminance[1] + 0.05)


def test_ui_text_and_button_token_pairs_meet_wcag_contrast() -> None:
    low_contrast = [
        (foreground, background, _contrast_ratio(COLORS[foreground], COLORS[background]))
        for foreground, background in TEXT_BACKGROUND_PAIRS
        if _contrast_ratio(COLORS[foreground], COLORS[background]) < 4.5
    ]
    assert not low_contrast, f"Token pairs below 4.5:1: {low_contrast}"


def test_badges_escape_dynamic_text_and_reject_untrusted_variants() -> None:
    payload = "<script>alert(1)</script>"

    for markup in (badge_html(payload, variant="danger"), role_badge(payload)):
        assert payload not in markup
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in markup

    unknown_sensitivity = sensitivity_badge(payload)
    assert payload not in unknown_sensitivity
    assert "Unknown sensitivity" in unknown_sensitivity

    unsafe_variant = badge_html("Safe label", variant='danger" onclick="alert(1)')
    assert re.search(r'class="ht-badge ht-badge--neutral"', unsafe_variant)
    assert "onclick" not in unsafe_variant


def _counts(**overrides: object) -> dict:
    counts = {
        "sources": 2, "evidence": 4, "claims": 3, "pending": 0, "approved": 3,
        "unvalidated": 0, "open_gaps": 0, "interview_questions": 0, "released": False,
        "draft_questions": 0, "sent_questions": 0, "answered_questions": 0,
        "releasable": 3, "approved_excluded": 0, "release_version": 0,
        "release_acknowledged": False, "release_needed": True,
    }
    counts.update(overrides)
    return counts


def test_next_step_follows_the_workflow_from_sources_to_acknowledgement() -> None:
    from ui import next_step

    def target(**overrides: object) -> tuple[str, str]:
        return next_step(_counts(**overrides), "Reviewer")["primary"]

    assert target(sources=0)[1] == "pages/1_Upload_Sources.py"
    assert target(evidence=0)[0] == "Parse sources"
    assert target(claims=0)[0] == "Extract claims"
    assert target(unvalidated=2)[0] == "Validate claims"
    assert target(pending=1)[0] == "Review claims"
    assert target()[0] == "Release handover"
    assert target(release_version=1, release_needed=False)[0] == "View released handover"


def test_open_gaps_never_hide_the_release_action() -> None:
    from ui import next_step

    guidance = next_step(_counts(open_gaps=5), "Admin")
    assert guidance["primary"] == ("Prepare exit interview", "pages/4_Exit_Interview.py")
    assert guidance["secondary"] == ("Release handover", "pages/3_Handover_View.py")

    after_interview = next_step(_counts(open_gaps=5, answered_questions=1), "Admin")
    assert after_interview["primary"] == ("Release handover", "pages/3_Handover_View.py")

    partially_reviewed = next_step(_counts(pending=2), "Reviewer")
    assert partially_reviewed["secondary"] == ("Release handover", "pages/3_Handover_View.py")


def test_next_step_keeps_restricted_roles_on_their_own_page() -> None:
    from ui import next_step

    assert next_step(_counts(), "Incoming")["primary"][1] == "pages/3_Handover_View.py"
    assert next_step(_counts(), "Departing")["primary"][1] == "pages/4_Exit_Interview.py"
    assert next_step(_counts(), "Departing")["secondary"] is None
