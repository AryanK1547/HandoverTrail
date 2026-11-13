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
