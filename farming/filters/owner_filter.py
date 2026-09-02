"""
Atlas Real Estate Farming - Owner Filter Classifier
Analyzes property listings/posts and filters out broker/agent posts,
retaining strictly direct-owner (FSBO) listings.
"""

import re
from typing import Dict, Any, Tuple, Optional

# Negative Keywords: Broker / Agency signals
# Focus strictly on agency traits: Line@, loan services, consulting services, co-agent splits, franchise names
# Note: "นายหน้า" alone is NOT a broker keyword as owners frequently write "รับนายหน้า", "ยินดีรับนายหน้า", or "ไม่รับนายหน้า"
BROKER_PATTERNS = [
    # 1. Line Official Account / Line@ (Commercial agents)
    r"line\s*@",
    r"line\s*(?:id)?\s*[:=\-]?\s*@\w+",
    r"lin\.ee/",
    r"line\s*official",
    
    # 2. Loan & Financing services
    r"บริการ(?:ยื่น)?สินเชื่อ",
    r"บริการยื่นกู้ให้?ฟรี",
    r"ยื่นกู้ให้ฟรีทุกขั้นตอน",
    r"ดูแลสินเชื่อฟรี",
    r"ปรึกษาสินเชื่อฟรี",
    r"พร้อมบริการด้านสินเชื่อ",
    r"บริการด้านสินเชื่อ",
    r"เช็ควงเงินฟรี",
    r"ดันเคส",
    r"กู้ได้เต็ม(?:\s*100%)?",
    
    # 3. Agency & Consulting services
    r"บริการให้คำปรึกษา",
    r"ปรึกษาฟรี",
    r"รับฝากขาย",
    r"รับฝากเช่า",
    r"รับจัดหา(?:บ้าน|คอนโด|ที่ดิน)",
    r"ศูนย์รับฝากขาย",
    r"บริษัทรับฝากขาย",
    r"ตัวแทนขายอสังหา",
    r"นายหน้าอสังหา(?:ริมทรัพย์)?",
    r"สังกัด\b",
    r"ทีมงานเอเจ้นท์",
    r"ทีมงานมืออาชีพ",
    r"ทีมงานคุณภาพ",
    r"ดูแลจนถึงวันโอน",
    r"ปิดการขายไว",
    r"พานำชม",
    r"ทำการตลาดฟรีจนกว่าจะขายได้",
    
    # 4. Co-broker / Co-agent agreements
    r"ยินดีรับ(?:โค|co)",
    r"ยินดีรับ\s*co-?agent",
    r"ยินดีรับ\s*co-?broker",
    r"(?<!ไม่)รับ\s*co(?:-?agent)?",
    r"(?<!ไม่)รับโค(?:เอเจ้นท์)?",
    r"ยินดีร่วมงานกับตัวแทน",
    
    # 5. Brokerage Franchises / Companies
    r"winner\s*estate",
    r"era\s*(?:thailand)?",
    r"realty\s*one",
    r"century\s*21",
    r"re/?max",
    r"tooktee",
    r"prop2share",
    r"living\s*insider\s*agent"
]

# Explicit Rejections of Brokers by Owners -> HIGH POSITIVE SIGNALS (Owner Direct)
OWNER_REJECTION_OF_BROKERS = [
    r"ไม่รับนายหน้า",
    r"งดรับนายหน้า",
    r"ไม่ต้อนรับนายหน้า",
    r"ไม่ผ่านนายหน้า",
    r"งดนายหน้า",
    r"งดรับ\s*co",
    r"งดรับโค",
    r"no\s*agent",
    r"no\s*broker",
    r"no\s*co-?agent"
]

# Positive Keywords: Indicates direct owner listing (including owners open to agents)
OWNER_POSITIVE_PATTERNS = [
    r"เจ้าของขายเอง",
    r"เจ้าของปล่อยเอง",
    r"ขายเองไม่ผ่านนายหน้า",
    r"ย้ายกลับต่างจังหวัด",
    r"บ้านของตัวเอง",
    r"ขายบ้านตัวเอง",
    r"ห้องของตัวเอง",
    r"เจ้าของดูแลเอง",
    r"เจ้าของบ้านขายเอง",
    # Owners seeking or welcoming sales agents to help sell:
    r"รับนายหน้า(?:ช่วยขาย)?",
    r"ยินดีรับนายหน้า",
    r"เปิดรับนายหน้า",
    r"นายหน้าทัก(?:มา)?ได้",
    r"ให้ค่านายหน้า",
    r"ค่านายหน้า\s*3%",
    r"ค่าคอม\s*3%"
]

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', str(text)).strip()

def extract_phone_numbers(text: str) -> list[str]:
    """Extract Thai mobile / landline phone numbers."""
    pattern = r'(?:0[689]\d{1}[- ]?\d{3}[- ]?\d{4})|(?:0[23457]\d{1}[- ]?\d{3}[- ]?\d{4})'
    raw_matches = re.findall(pattern, text)
    cleaned = []
    for m in raw_matches:
        digits = re.sub(r'\D', '', m)
        if len(digits) in (9, 10):
            formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if len(digits) == 10 else f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
            if formatted not in cleaned:
                cleaned.append(formatted)
    return cleaned

def extract_line_id(text: str) -> Optional[str]:
    """Extract Line ID from text."""
    match = re.search(r'(?:line\s*id|line|id)\s*[:=\-]?\s*([a-zA-Z0-9._\-@]+)', text, re.IGNORECASE)
    if match:
        val = match.group(1).strip()
        if len(val) >= 3 and not val.lower() in ('me', 'link', 'http', 'https', 'com'):
            return val
    return None

def extract_asking_price(text: str) -> Optional[int]:
    """Extract price in Thai Baht from text."""
    # Pattern 1: X.XX ล้าน or X ล้านบาท
    match_millions = re.search(r'(\d+(?:\.\d+)?)\s*(?:ล้าน|ลบ\b|ล\.)', text, re.IGNORECASE)
    if match_millions:
        try:
            val = float(match_millions.group(1))
            return int(val * 1_000_000)
        except ValueError:
            pass

    # Pattern 2: Standard number with commas e.g. 3,500,000 or 450,000
    match_commas = re.search(r'(?:ราคา|ขายเพียง|ขาย|เสนอขาย)?\s*(\d{1,3}(?:,\d{3})+)\s*(?:บาท|.-)?', text)
    if match_commas:
        try:
            val = int(match_commas.group(1).replace(',', ''))
            if 300_000 <= val <= 200_000_000:
                return val
        except ValueError:
            pass

    # Pattern 3: Plain digits e.g. 3500000
    match_digits = re.search(r'(?:ราคา|ขาย)\s*(\d{6,8})\s*(?:บาท)?', text)
    if match_digits:
        try:
            val = int(match_digits.group(1))
            if 300_000 <= val <= 200_000_000:
                return val
        except ValueError:
            pass

    return None

def extract_property_specs(text: str) -> Dict[str, Any]:
    """Extract beds, baths, sqw, sqm, and location clues from post text."""
    specs: Dict[str, Any] = {
        "bed": None,
        "bath": None,
        "sqw": None,
        "sqm": None,
        "phones": extract_phone_numbers(text),
        "lineId": extract_line_id(text),
        "extractedPrice": extract_asking_price(text)
    }

    # Bedrooms
    bed_match = re.search(r'(\d+)\s*(?:ห้องนอน|นอน)', text)
    if bed_match:
        specs["bed"] = int(bed_match.group(1))

    # Bathrooms
    bath_match = re.search(r'(\d+)\s*(?:ห้องน้ำ|น้ำ)', text)
    if bath_match:
        specs["bath"] = int(bath_match.group(1))

    # Land size (ตร.ว.)
    sqw_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ตร\.?ว\.?|ตารางวา)', text)
    if sqw_match:
        try:
            specs["sqw"] = float(sqw_match.group(1))
        except ValueError:
            pass

    # Usable size (ตร.ม.)
    sqm_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ตร\.?ม\.?|ตารางเมตร)', text)
    if sqm_match:
        try:
            specs["sqm"] = float(sqm_match.group(1))
        except ValueError:
            pass

    return specs

def classify_listing(
    text: str,
    author_name: str = "",
    explicit_owner_tag: bool = False,
    min_confidence: float = 0.70
) -> Tuple[bool, float, Dict[str, Any]]:
    """
    Classify whether a post/listing is from a direct owner (FSBO) or an agent/broker.
    Returns:
        (is_direct_owner, confidence_score, details_dict)
    """
    full_text = f"{author_name} {text}".lower()

    # Pre-check: Check if owner is rejecting brokers e.g. "ไม่รับนายหน้า", "ไม่รับ co"
    owner_rejections = []
    for pat in OWNER_REJECTION_OF_BROKERS:
        if re.search(pat, full_text, re.IGNORECASE):
            owner_rejections.append(pat)

    # Sanitize text for broker search so "ไม่รับนายหน้า" doesn't falsely trigger "นายหน้า"
    sanitized_for_broker_check = full_text
    for pat in OWNER_REJECTION_OF_BROKERS:
        sanitized_for_broker_check = re.sub(pat, " [owner_rejects_broker] ", sanitized_for_broker_check)

    # 1. Check for negative broker keywords on sanitized text
    broker_hits = []
    for pat in BROKER_PATTERNS:
        if re.search(pat, sanitized_for_broker_check, re.IGNORECASE):
            broker_hits.append(pat)
            
    # 2. Check for positive owner keywords
    owner_hits = []
    for pat in OWNER_POSITIVE_PATTERNS:
        if re.search(pat, full_text, re.IGNORECASE):
            owner_hits.append(pat)

    # Combined positive hits (explicit owner statements + broker rejections)
    all_owner_signals = owner_hits + owner_rejections

    # 3. Decision Logic
    confidence = 0.5
    is_direct_owner = False
    
    if explicit_owner_tag:
        # ZmyHome official badge 'เจ้าของขายเอง'
        confidence = 0.98
        is_direct_owner = True
        # If strong broker keywords appear in description, invalidate
        if len(broker_hits) >= 2:
            confidence = 0.2
            is_direct_owner = False
    elif len(broker_hits) > 0:
        # Broker signals detected
        is_direct_owner = False
        confidence = max(0.05, 0.25 - (len(broker_hits) * 0.1))
    elif len(all_owner_signals) > 0:
        # Strong direct-owner signals
        is_direct_owner = True
        confidence = min(0.98, 0.80 + (len(all_owner_signals) * 0.08))
    else:
        # Neutral post without broker terms and without explicit owner badge
        has_phone = len(extract_phone_numbers(text)) > 0
        if has_phone:
            confidence = 0.65
            is_direct_owner = confidence >= min_confidence
        else:
            confidence = 0.40
            is_direct_owner = False

    details = {
        "isDirectOwner": is_direct_owner,
        "confidence": round(confidence, 2),
        "brokerKeywordsFound": broker_hits,
        "ownerKeywordsFound": all_owner_signals,
        "specs": extract_property_specs(text)
    }

    return is_direct_owner, round(confidence, 2), details

