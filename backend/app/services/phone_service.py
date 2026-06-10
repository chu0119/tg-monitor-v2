"""手机号解析服务 - 基于 Google phonenumbers 库"""
import phonenumbers
from phonenumbers import geocoder, carrier as ph_carrier, timezone as ph_tz
from typing import Optional, Tuple

# 国家代码 → 国家名
COUNTRY_NAMES = {
    "CN": "中国", "HK": "香港", "MO": "澳门", "TW": "台湾",
    "US": "美国", "CA": "加拿大", "GB": "英国", "JP": "日本",
    "KR": "韩国", "AU": "澳大利亚", "DE": "德国", "FR": "法国",
    "IN": "印度", "ID": "印尼", "TH": "泰国", "PH": "菲律宾",
    "VN": "越南", "MY": "马来西亚", "SG": "新加坡", "RU": "俄罗斯",
    "BR": "巴西", "MX": "墨西哥", "ES": "西班牙", "IT": "意大利",
    "NL": "荷兰", "SE": "瑞典", "NO": "挪威", "TR": "土耳其",
    "SA": "沙特", "AE": "阿联酋", "EG": "埃及", "ZA": "南非",
    "PK": "巴基斯坦", "BD": "孟加拉", "NG": "尼日利亚",
}


# 已知国家代码前缀 → 区域映射
PREFIX_REGION_MAP = {
    "86": "CN", "852": "HK", "853": "MO", "886": "TW",
    "44": "GB", "81": "JP", "82": "KR", "61": "AU",
    "33": "DE", "39": "IT", "91": "IN", "62": "ID",
    "66": "TH", "63": "PH", "84": "VN", "60": "MY",
    "65": "SG", "90": "TR", "966": "SA", "971": "AE",
    "7": "RU", "55": "BR", "52": "MX", "34": "ES",
    "31": "NL", "46": "SE", "47": "NO", "380": "UA",
    "855": "KH", "95": "MM", "977": "NP", "94": "LK",
}


def parse_phone(phone: str) -> Optional[phonenumbers.PhoneNumber]:
    """解析手机号 - 智能区域检测"""
    if not phone or not phone.strip():
        return None
    try:
        normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

        # 带+号的直接解析
        if normalized.startswith("+"):
            return phonenumbers.parse(normalized, None)

        # 没有+号的，尝试加+解析
        if normalized.startswith("86") and len(normalized) >= 13:
            return phonenumbers.parse("+" + normalized, None)

        # 中国11位手机号（以1开头）
        if len(normalized) == 11 and normalized.startswith("1"):
            return phonenumbers.parse("+86" + normalized, None)

        # 尝试匹配已知国家代码前缀
        for prefix, region in sorted(PREFIX_REGION_MAP.items(), key=lambda x: -len(x[0])):
            if normalized.startswith(prefix):
                try:
                    return phonenumbers.parse("+" + normalized, region)
                except Exception:
                    continue

        # 兜底：用中国区域解析
        return phonenumbers.parse(normalized, "CN")
    except Exception:
        return None


def get_country_info(phone: str) -> Tuple[str, str]:
    """获取国家代码和国家名"""
    pn = parse_phone(phone)
    if not pn:
        return ("", "")
    region = phonenumbers.region_code_for_number(pn)
    if not region:
        return ("", "未知")
    country_name = COUNTRY_NAMES.get(region, region)
    return (region, country_name)


def get_carrier_name(phone: str) -> str:
    """获取运营商名称"""
    pn = parse_phone(phone)
    if not pn:
        return ""
    name = ph_carrier.name_for_number(pn, "zh")
    return name or ""


def get_location_name(phone: str) -> str:
    """获取归属地"""
    pn = parse_phone(phone)
    if not pn:
        return ""
    name = geocoder.description_for_number(pn, "zh")
    return name or ""


def get_full_info(phone: str) -> dict:
    """获取手机号完整信息"""
    if not phone:
        return {"raw": "", "country_code": "", "country": "", "carrier": "", "location": ""}
    
    pn = parse_phone(phone)
    if not pn:
        return {"raw": phone, "country_code": "", "country": "", "carrier": "", "location": ""}
    
    region = phonenumbers.region_code_for_number(pn) or ""
    country_name = COUNTRY_NAMES.get(region, region)
    carrier = ph_carrier.name_for_number(pn, "zh") or ""
    location = geocoder.description_for_number(pn, "zh") or ""
    
    return {
        "raw": phone,
        "country_code": region,
        "country": country_name,
        "carrier": carrier,
        "location": location,
    }


def normalize_phone(phone: str) -> str:
    """标准化手机号"""
    if not phone:
        return ""
    pn = parse_phone(phone)
    if pn and phonenumbers.is_valid_number(pn):
        return phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.E164)
    return phone
