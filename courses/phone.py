"""Country dial codes and E.164 mobile number helpers."""

from __future__ import annotations

import re


# India first (default), then alphabetical by country name.
COUNTRY_CHOICES = [
    ("91", "India (+91)"),
    ("93", "Afghanistan (+93)"),
    ("355", "Albania (+355)"),
    ("213", "Algeria (+213)"),
    ("54", "Argentina (+54)"),
    ("374", "Armenia (+374)"),
    ("61", "Australia (+61)"),
    ("43", "Austria (+43)"),
    ("994", "Azerbaijan (+994)"),
    ("973", "Bahrain (+973)"),
    ("880", "Bangladesh (+880)"),
    ("375", "Belarus (+375)"),
    ("32", "Belgium (+32)"),
    ("975", "Bhutan (+975)"),
    ("591", "Bolivia (+591)"),
    ("387", "Bosnia (+387)"),
    ("55", "Brazil (+55)"),
    ("673", "Brunei (+673)"),
    ("359", "Bulgaria (+359)"),
    ("855", "Cambodia (+855)"),
    ("237", "Cameroon (+237)"),
    ("56", "Chile (+56)"),
    ("86", "China (+86)"),
    ("57", "Colombia (+57)"),
    ("506", "Costa Rica (+506)"),
    ("385", "Croatia (+385)"),
    ("357", "Cyprus (+357)"),
    ("420", "Czechia (+420)"),
    ("45", "Denmark (+45)"),
    ("20", "Egypt (+20)"),
    ("372", "Estonia (+372)"),
    ("251", "Ethiopia (+251)"),
    ("358", "Finland (+358)"),
    ("33", "France (+33)"),
    ("995", "Georgia (+995)"),
    ("49", "Germany (+49)"),
    ("233", "Ghana (+233)"),
    ("30", "Greece (+30)"),
    ("852", "Hong Kong (+852)"),
    ("36", "Hungary (+36)"),
    ("354", "Iceland (+354)"),
    ("62", "Indonesia (+62)"),
    ("98", "Iran (+98)"),
    ("964", "Iraq (+964)"),
    ("353", "Ireland (+353)"),
    ("972", "Israel (+972)"),
    ("39", "Italy (+39)"),
    ("225", "Ivory Coast (+225)"),
    ("81", "Japan (+81)"),
    ("962", "Jordan (+962)"),
    ("7", "Kazakhstan (+7)"),
    ("254", "Kenya (+254)"),
    ("965", "Kuwait (+965)"),
    ("996", "Kyrgyzstan (+996)"),
    ("856", "Laos (+856)"),
    ("371", "Latvia (+371)"),
    ("961", "Lebanon (+961)"),
    ("218", "Libya (+218)"),
    ("370", "Lithuania (+370)"),
    ("352", "Luxembourg (+352)"),
    ("853", "Macau (+853)"),
    ("60", "Malaysia (+60)"),
    ("960", "Maldives (+960)"),
    ("52", "Mexico (+52)"),
    ("373", "Moldova (+373)"),
    ("976", "Mongolia (+976)"),
    ("212", "Morocco (+212)"),
    ("95", "Myanmar (+95)"),
    ("977", "Nepal (+977)"),
    ("31", "Netherlands (+31)"),
    ("64", "New Zealand (+64)"),
    ("234", "Nigeria (+234)"),
    ("389", "North Macedonia (+389)"),
    ("47", "Norway (+47)"),
    ("968", "Oman (+968)"),
    ("92", "Pakistan (+92)"),
    ("970", "Palestine (+970)"),
    ("507", "Panama (+507)"),
    ("51", "Peru (+51)"),
    ("63", "Philippines (+63)"),
    ("48", "Poland (+48)"),
    ("351", "Portugal (+351)"),
    ("974", "Qatar (+974)"),
    ("40", "Romania (+40)"),
    ("7", "Russia (+7)"),
    ("250", "Rwanda (+250)"),
    ("966", "Saudi Arabia (+966)"),
    ("221", "Senegal (+221)"),
    ("381", "Serbia (+381)"),
    ("65", "Singapore (+65)"),
    ("421", "Slovakia (+421)"),
    ("386", "Slovenia (+386)"),
    ("27", "South Africa (+27)"),
    ("82", "South Korea (+82)"),
    ("34", "Spain (+34)"),
    ("94", "Sri Lanka (+94)"),
    ("249", "Sudan (+249)"),
    ("46", "Sweden (+46)"),
    ("41", "Switzerland (+41)"),
    ("963", "Syria (+963)"),
    ("886", "Taiwan (+886)"),
    ("992", "Tajikistan (+992)"),
    ("255", "Tanzania (+255)"),
    ("66", "Thailand (+66)"),
    ("216", "Tunisia (+216)"),
    ("90", "Turkey (+90)"),
    ("993", "Turkmenistan (+993)"),
    ("256", "Uganda (+256)"),
    ("380", "Ukraine (+380)"),
    ("971", "United Arab Emirates (+971)"),
    ("44", "United Kingdom (+44)"),
    ("1", "United States / Canada (+1)"),
    ("998", "Uzbekistan (+998)"),
    ("58", "Venezuela (+58)"),
    ("84", "Vietnam (+84)"),
    ("967", "Yemen (+967)"),
    ("260", "Zambia (+260)"),
    ("263", "Zimbabwe (+263)"),
]

DEFAULT_COUNTRY_CODE = "91"
_DIAL_CODES = tuple(
    sorted({code for code, _label in COUNTRY_CHOICES}, key=len, reverse=True)
)


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def compose_e164(country_code: str, national: str) -> str:
    """Build a canonical +<country><number> value from the signup fields."""
    cc = digits_only(country_code)
    if not cc:
        raise ValueError("Select a country code.")
    number = digits_only(national)
    if number.startswith("00"):
        number = number[2:]
    if number.startswith("0"):
        number = number.lstrip("0")
    if number.startswith(cc) and len(number) - len(cc) >= 6:
        number = number[len(cc) :]
    if cc == "91":
        if not (len(number) == 10 and number[0] in "6789"):
            raise ValueError("Enter a valid 10-digit Indian mobile number.")
    elif not (6 <= len(number) <= 12):
        raise ValueError("Enter a valid mobile number for the selected country.")
    return f"+{cc}{number}"


def to_e164(mobile: str, default_cc: str = DEFAULT_COUNTRY_CODE) -> str:
    """Normalize a stored or typed number to E.164 (+country and digits)."""
    raw = (mobile or "").strip()
    if not raw:
        return ""
    if raw.startswith("+"):
        number = digits_only(raw)
        return f"+{number}" if number else ""
    number = digits_only(raw)
    if number.startswith("00"):
        number = number[2:]
        return f"+{number}" if number else ""
    if len(number) == 11 and number.startswith("0"):
        number = number[1:]
    if len(number) == 10:
        return f"+{default_cc}{number}"
    if len(number) == 12 and number.startswith("91"):
        return f"+{number}"
    return f"+{number}" if number else ""


def split_e164(mobile: str) -> tuple[str, str]:
    """Return (country_code, national_number) from a stored mobile value."""
    number = digits_only(to_e164(mobile) or mobile)
    if not number:
        return DEFAULT_COUNTRY_CODE, ""
    for code in _DIAL_CODES:
        if number.startswith(code) and len(number) > len(code):
            return code, number[len(code) :]
    if len(number) == 10:
        return DEFAULT_COUNTRY_CODE, number
    return DEFAULT_COUNTRY_CODE, number


def mobile_lookup_values(mobile: str) -> list[str]:
    """All formats that may already be stored for the same phone number."""
    e164 = to_e164(mobile)
    number = digits_only(e164 or mobile)
    if not number:
        return []
    values = {e164, number, f"+{number}"}
    cc, national = split_e164(e164 or mobile)
    if national:
        values.update({national, f"+{national}", f"{cc}{national}", f"+{cc}{national}"})
    if cc == "91" and len(national) == 10:
        values.update({national, f"91{national}", f"+91{national}"})
    elif len(number) == 10:
        values.update({f"91{number}", f"+91{number}"})
    return [value for value in values if value]


def mobile_is_registered(mobile: str, exclude_user_id=None) -> bool:
    from courses.models import StudentProfile

    values = mobile_lookup_values(mobile)
    if not values:
        return False
    qs = StudentProfile.objects.filter(mobile_number__in=values).exclude(
        mobile_number__isnull=True
    )
    if exclude_user_id is not None:
        qs = qs.exclude(user_id=exclude_user_id)
    return qs.exists()


def mask_mobile(mobile: str) -> str:
    cc, national = split_e164(mobile)
    if len(national) < 4:
        return f"+{cc} ****" if cc else "****"
    hidden = "*" * max(len(national) - 4, 4)
    return f"+{cc} {hidden}{national[-4:]}"
