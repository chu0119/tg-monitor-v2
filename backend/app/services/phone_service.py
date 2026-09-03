"""手机号码解析服务 - 基于 Google phonenumbers 库"""
import phonenumbers
from phonenumbers import geocoder, carrier as ph_carrier, timezone as ph_tz, PhoneNumberMatcher
from typing import Optional, Tuple

# 国家代码 -> 中文名
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
    "CU": "古巴", "KZ": "哈萨克斯坦", "KH": "柬埔寨",
    "MM": "缅甸", "NP": "尼泊尔", "LK": "斯里兰卡",
    "UA": "乌克兰", "PL": "波兰", "PT": "葡萄牙", "CL": "智利",
    "CO": "哥伦比亚", "AR": "阿根廷", "PE": "秘鲁",
    "PH": "菲律宾", "BD": "孟加拉", "EG": "埃及",
    "KE": "肯尼亚", "GH": "加纳", "TZ": "坦桑尼亚",
    "MR": "毛里塔尼亚", "GL": "格陵兰", "AF": "阿富汗",
    "IR": "伊朗", "IQ": "伊拉克", "SY": "叙利亚",
    "LY": "利比亚", "TN": "突尼斯", "DZ": "阿尔及利亚",
    "MA": "摩洛哥", "SD": "苏丹", "ET": "埃塞俄比亚",
    "SO": "索马里", "SN": "塞内加尔", "ML": "马里",
    "BF": "布基纳法索", "NE": "尼日尔", "TD": "乍得",
    "CM": "喀麦隆", "GA": "加蓬", "CG": "刚果",
    "CD": "刚果(金)", "AO": "安哥拉", "ZM": "赞比亚",
    "ZW": "津巴布韦", "MG": "马达加斯加", "MZ": "莫桑比克",
    "NA": "纳米比亚", "BW": "博茨瓦纳", "SZ": "斯威士兰",
    "LS": "莱索托", "KM": "科摩罗", "DJ": "吉布提",
    "ER": "厄立特里亚", "SS": "南苏丹", "CF": "中非",
    "GQ": "赤道几内亚", "ST": "圣多美和普林西比",
    "SC": "塞舌尔", "MU": "毛里求斯", "RE": "留尼汪",
    "GM": "冈比亚", "GN": "几内亚", "GW": "几内亚比绍",
    "SL": "塞拉利昂", "LR": "利比里亚", "TG": "多哥",
    "BJ": "贝宁", "CV": "佛得角",
    "PG": "巴布亚新几内亚", "FJ": "斐济", "WS": "萨摩亚",
    "TO": "汤加", "VU": "瓦努阿图", "SB": "所罗门群岛",
    "MN": "蒙古", "KG": "吉尔吉斯斯坦", "TJ": "塔吉克斯坦",
    "TM": "土库曼斯坦", "UZ": "乌兹别克斯坦",
    "BT": "不丹", "MV": "马尔代夫", "BN": "文莱",
    "TL": "东帝汶", "GE": "格鲁吉亚", "AM": "亚美尼亚",
    "AZ": "阿塞拜疆", "CY": "塞浦路斯", "MT": "马耳他",
    "IS": "冰岛", "AL": "阿尔巴尼亚", "BA": "波黑",
    "ME": "黑山", "MK": "北马其顿", "RS": "塞尔维亚",
    "XK": "科索沃", "MD": "摩尔多瓦", "BY": "白俄罗斯",
    "LT": "立陶宛", "LV": "拉脱维亚", "EE": "爱沙尼亚",
    "SI": "斯洛文尼亚", "HR": "克罗地亚", "SK": "斯洛伐克",
    "CZ": "捷克", "HU": "匈牙利", "BG": "保加利亚",
    "RO": "罗马尼亚", "GR": "希腊", "AT": "奥地利",
    "CH": "瑞士", "BE": "比利时", "IE": "爱尔兰",
    "LU": "卢森堡", "FI": "芬兰", "DK": "丹麦",
    "PT": "葡萄牙", "AD": "安道尔", "MC": "摩纳哥",
    "SM": "圣马力诺", "VA": "梵蒂冈", "LI": "列支敦士登",
    "GI": "直布罗陀", "FO": "法罗群岛",
    "JM": "牙买加", "TT": "特立尼达和多巴哥", "BB": "巴巴多斯",
    "BS": "巴哈马", "GY": "圭亚那", "SR": "苏里南",
    "EC": "厄瓜多尔", "BO": "玻利维亚", "PY": "巴拉圭",
    "UY": "乌拉圭", "CR": "哥斯达黎加", "PA": "巴拿马",
    "HN": "洪都拉斯", "SV": "萨尔瓦多", "GT": "危地马拉",
    "BZ": "伯利兹", "NI": "尼加拉瓜", "CU": "古巴",
    "DO": "多米尼加", "HT": "海地", "PR": "波多黎各",
    "VE": "委内瑞la", "GP": "瓜德罗普", "MQ": "马提尼克",
    "GF": "法属圭亚那", "CW": "库拉索", "AW": "阿鲁巴",
    "BQ": "博内尔", "SX": "圣马丁", "MF": "法属圣马丁",
    "BL": "圣巴泰勒米", "AI": "安圭拉", "VG": "英属维尔京群岛",
    "TC": "特克斯和凯科斯群岛", "KY": "开曼群岛",
    "BM": "百慕大", "VI": "美属维尔京群岛",
    "GU": "关岛", "AS": "美属萨摩亚",
    "CK": "库克群岛", "NU": "纽埃", "TK": "托克劳",
    "PN": "皮特凯恩群岛", "NF": "诺福克岛",
    "CX": "圣诞岛", "CC": "科科斯群岛",
    "SH": "圣赫勒拿", "MS": "蒙特塞拉特",
    "KN": "圣基茨和尼维斯", "AG": "安提瓜和巴布达",
    "DM": "多米尼克", "LC": "圣卢西亚",
    "VC": "圣文森特和格林纳丁斯", "GD": "格林纳达",
    "BM": "百慕大",
}

# Telegram 内部服务号码前缀（验证码、通知等），不属于任何国家
TELEGRAM_SERVICE_PREFIXES = ("8880", "8881", "8882", "8883", "8884", "8885")


def parse_phone(phone: str) -> Optional[phonenumbers.PhoneNumber]:
    """解析手机号 - 返回 phonenumbers.PhoneNumber 对象
    
    核心策略：
    1. 有+号的直接解析（最可靠）
    2. 中国11位手机号（1开头）自动补+86
    3. 其他号码统一加+号让 phonenumbers 库自动识别
    4. 绝不默认按某个国家解析（避免误判）
    """
    if not phone or not phone.strip():
        return None
    try:
        normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

        if not normalized or not normalized.isdigit():
            return None

        # Telegram 服务号码，跳过
        for prefix in TELEGRAM_SERVICE_PREFIXES:
            if normalized.startswith(prefix):
                return None

        # 有+号的直接解析
        if normalized.startswith("+"):
            return phonenumbers.parse(normalized, None)

        # 中国11位手机号（1开头，非8880前缀）
        if len(normalized) == 11 and normalized.startswith("1"):
            return phonenumbers.parse("+86" + normalized, None)

        # 其他所有号码：加+号，让 phonenumbers 库自动判断国家
        # phonenumbers 库内置了全球所有国家代码数据，比手动维护的前缀表准确得多
        try:
            return phonenumbers.parse("+" + normalized, None)
        except phonenumbers.NumberParseException:
            # 尝试作为中国号码解析（86开头但长度不足13位的情况）
            if normalized.startswith("86"):
                try:
                    return phonenumbers.parse("+86" + normalized[2:], None)
                except Exception:
                    pass
            return None
    except Exception:
        return None


# country_code (numeric) -> region code 映射，用于 region_code_for_number 返回 None 时的 fallback
# 涵盖多地区国家码（如 44→GB/GG/IM）
_CODE_TO_REGION = {
    1: "US", 7: "RU", 20: "EG", 27: "ZA", 30: "GR", 31: "NL", 32: "BE",
    33: "FR", 34: "ES", 36: "HU", 39: "IT", 40: "RO", 41: "CH", 43: "AT",
    44: "GB", 45: "DK", 46: "SE", 47: "NO", 48: "PL", 49: "DE", 51: "PE",
    52: "MX", 53: "CU", 54: "AR", 55: "BR", 56: "CL", 57: "CO", 58: "VE",
    60: "ID", 61: "AU", 62: "ID", 63: "PH", 64: "NZ", 65: "SG", 66: "TH",
    81: "JP", 82: "KR", 84: "VN", 86: "CN", 90: "TR", 91: "IN", 92: "PK",
    93: "AF", 94: "LK", 95: "MM", 98: "IR", 212: "MA", 213: "DZ", 216: "TN",
    218: "LY", 220: "GM", 221: "SN", 222: "MR", 223: "ML", 224: "GN",
    225: "CI", 226: "BF", 227: "NE", 228: "TG", 229: "BJ", 230: "MU",
    231: "LR", 232: "SL", 233: "GH", 234: "NG", 235: "TD", 236: "CF",
    237: "CM", 240: "GQ", 241: "GA", 242: "CG", 243: "CD", 244: "AO",
    245: "GW", 246: "IO", 248: "SC", 249: "SD", 250: "RW", 251: "ET",
    252: "SO", 253: "DJ", 254: "KE", 255: "TZ", 256: "UG", 257: "BI",
    258: "MZ", 260: "ZM", 261: "MG", 262: "RE", 263: "ZW", 264: "NA",
    265: "MW", 266: "LS", 267: "BW", 268: "SZ", 269: "KM", 290: "SH",
    291: "ER", 297: "AW", 298: "FO", 299: "GL", 350: "GI", 351: "PT",
    352: "LU", 353: "IE", 354: "IS", 355: "AL", 356: "MT", 357: "CY",
    358: "FI", 359: "BG", 370: "LT", 371: "LV", 372: "EE", 373: "MD",
    374: "AM", 375: "BY", 376: "AD", 377: "MC", 378: "SM", 379: "VA",
    380: "UA", 381: "RS", 382: "ME", 385: "HR", 386: "SI", 387: "BA",
    389: "MK", 420: "CZ", 421: "SK", 852: "HK", 853: "MO", 855: "KH",
    856: "LA", 880: "BD", 886: "TW",
}


def get_country_info(phone: str) -> Tuple[str, str]:
    """获取国家代码和国家名"""
    pn = parse_phone(phone)
    if not pn:
        return ("", "")
    region = phonenumbers.region_code_for_number(pn)
    if not region:
        # Fallback: 用数字国家码查找区域
        region = _CODE_TO_REGION.get(pn.country_code, "")
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
    if not region:
        region = _CODE_TO_REGION.get(pn.country_code, "")
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


# ============================================================
# 手机号文本提取功能
# ============================================================

def extract_phones_from_text(text: str, default_region: str = "CN") -> list:
    """从文本中提取所有可能的手机号码

    使用 phonenumbers.PhoneNumberMatcher 扫描文本，返回提取到的中国手机号。
    过滤条件：
    1. 必须是 possible number
    2. 只保留中国号码（country_code=86）
    3. 排除 Telegram 服务号码（8880前缀）

    返回: [{"phone": "13800138000", "display": "+86 138 0013 8000", "context": "前50字...手机号...后50字"}]
    """
    if not text or len(text) < 5:
        return []

    results = []
    seen = set()

    try:
        for match in PhoneNumberMatcher(text, default_region):
            pn = match.number
            # 只保留中国号码
            if pn.country_code != 86:
                continue
            # 只保留 possible number
            if not phonenumbers.is_possible_number(pn):
                continue
            # 获取本地号码（去掉国家码）
            national = str(pn.national_number)
            # 过滤 Telegram 服务号码
            if national.startswith("8880") or national.startswith("8881"):
                continue
            # 过滤明显不是手机号的（长度不对）
            if len(national) != 11:
                continue
            # 只保留有效中国手机号前缀 (13x-19x)
            prefix = int(national[1:3]) if national[1:3].isdigit() else 0
            if prefix < 30 or prefix > 99:
                continue

            if national in seen:
                continue
            seen.add(national)

            # 提取上下文（前后各50字符）
            start = max(0, match.start - 50)
            end = min(len(text), match.end + 50)
            context = text[start:end].strip()

            results.append({
                "phone": national,
                "display": text[match.start:match.end],
                "context": context,
            })
    except Exception as e:
        import sys
        print(f"extract_phones error: {e}", file=sys.stderr)

    return results


def extract_phones_from_message(message) -> list:
    """从 Telegram 消息对象中提取手机号

    扫描 message.text 和 message.caption 字段。
    返回: [{"phone": "13800138000", "display": "+86 138 0013 8000", "context": "..."}]
    """
    phones = []
    text = getattr(message, "text", None) or ""
    caption = getattr(message, "caption", None) or ""

    if text:
        phones.extend(extract_phones_from_text(text))
    if caption:
        phones.extend(extract_phones_from_text(caption))

    # 去重（基于 phone 字段）
    seen = set()
    unique = []
    for p in phones:
        if p["phone"] not in seen:
            seen.add(p["phone"])
            unique.append(p)

    return unique
