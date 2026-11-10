# -*- coding: utf-8 -*-
"""中国手机号段定位器（离线，基于 xluohome/phonedata 的 phone.dat）

数据文件格式（已逆向验证）：
  头部 8 字节: 版本号(4 ASCII) + 索引区起始偏移(4, LE uint32)
  记录区: 以 \\x00 分隔的记录，格式 `省|市|邮编|区号`
  索引区: 每条 9 字节 = 号段前缀(4, LE uint32) + 记录偏移(4, LE uint32) + 卡别(1)
           卡别: 1=移动 2=联通 3=电信 4+=虚拟运营商
  索引按前缀升序排列，可二分查找。号段前缀为 7 位（如 1300000）。

定位精度：省+市（号段级，运营商官方数据，比 phonenumbers 的地理库完整得多）。
"""
import bisect
import struct
from pathlib import Path
from typing import Optional, Dict

_DATA_FILE = Path(__file__).parent / "phone.dat"

# 卡别字节 -> 运营商（phone.dat 2302 版实测编码：
#   1=移动 2=联通 3=电信 4=电信虚商(162x) 5=联通虚商(167x)
#   6=移动物联(1349x) 7=中国广电(192x)）
CARD_CARRIER = {
    1: "中国移动",
    2: "中国联通",
    3: "中国电信",
    4: "中国电信",       # 电信虚商（162 号段）
    5: "中国联通",       # 联通虚商（167 号段）
    6: "中国移动",       # 移动物联（1349 卫星/物联）
    7: "中国广电",       # 广电 5G（192 号段，2021 放号）
}
# 虚拟运营商号段（1xx 第4位）——统一标注，比卡片字节更可靠
_VIRTUAL_PREFIX3 = {"162", "165", "167", "170", "171"}


class PhoneLocator:
    """phone.dat 离线定位器（单例，首次访问加载，二分查找 O(log n)）"""

    def __init__(self):
        self._loaded = False
        self._version = ""
        self._offset = 0
        self._data = b""
        self._prefixes = []      # 升序前缀列表（用于 bisect）
        self._index_start = 0
        self._index_count = 0
        self._record_cache: Dict[int, tuple] = {}  # 记录偏移 -> (省, 市, 邮编, 区号)

    def _ensure_loaded(self):
        if self._loaded:
            return
        if not _DATA_FILE.exists():
            self._loaded = True
            return
        self._data = _DATA_FILE.read_bytes()
        self._version = self._data[0:4].decode()
        self._offset = struct.unpack("<I", self._data[4:8])[0]
        # 索引条目数量 = (文件尾 - 索引起始) // 9
        self._index_start = self._offset
        self._index_count = (len(self._data) - self._offset) // 9
        # 预读全部前缀（每条 9 字节中的前 4 字节 LE）
        self._prefixes = [
            struct.unpack_from("<I", self._data, self._index_start + i * 9)[0]
            for i in range(self._index_count)
        ]
        self._loaded = True

    def lookup(self, digits: str) -> Optional[Dict]:
        """查询 7+ 位中国手机号。返回 {'province','city','zip','area_code','carrier'} 或 None"""
        self._ensure_loaded()
        if not self._data or len(digits) < 7:
            return None
        prefix = int(digits[:7])

        idx = bisect.bisect_left(self._prefixes, prefix)
        if idx >= self._index_count or self._prefixes[idx] != prefix:
            # 号段表按 7 位粒度全覆盖，找不到说明不是真实号段
            return None

        entry = self._index_start + idx * 9
        _, rec_off, card = struct.unpack_from("<II B", self._data, entry)

        rec = self._record_cache.get(rec_off)
        if rec is None:
            end = self._data.find(b"\x00", rec_off)
            if end == -1:
                end = self._index_start
            parts = self._data[rec_off:end].decode("utf-8", errors="replace").split("|")
            rec = (parts + ["", "", "", ""])[:4]
            self._record_cache[rec_off] = rec
        province, city, zip_code, area_code = rec

        carrier = CARD_CARRIER.get(card, "")
        if digits[:3] in _VIRTUAL_PREFIX3:
            carrier = f"{carrier}虚拟运营商" if carrier else "虚拟运营商"
        return {
            "province": province,
            "city": city,
            "zip": zip_code,
            "area_code": area_code,
            "carrier": carrier,
        }

    @property
    def version(self) -> str:
        self._ensure_loaded()
        return self._version

    @property
    def segment_count(self) -> int:
        self._ensure_loaded()
        return self._index_count


phone_locator = PhoneLocator()
