"""单元测试：_get_telethon_entity_id 覆盖多种chat_id格式"""
import pytest


def get_telethon_entity_id(chat_id: int) -> int:
    """将数据库chat_id转换为Telethon PeerChannel可用的正数ID"""
    if chat_id < -1000000000000:
        return abs(chat_id + 1000000000000)
    elif chat_id < 0:
        return abs(chat_id)
    return chat_id


class TestTelethonEntityId:
    """测试chat_id到entity.id的转换"""

    def test_channel_12digit_negative(self):
        """channel: 12位负数格式（实际数据库中的格式，如 -998518730431）"""
        chat_id = -998518730431
        result = get_telethon_entity_id(chat_id)
        assert result == 998518730431, f"期望 998518730431，得到 {result}"

    def test_channel_bot_api_100_prefix(self):
        """channel: Bot API -100前缀格式（13位，如 -1001234567890）"""
        chat_id = -1001234567890
        result = get_telethon_entity_id(chat_id)
        assert result == 1234567890, f"期望 1234567890，得到 {result}"

    def test_channel_100_prefix_edge(self):
        """channel: -100前缀边界值"""
        chat_id = -1000000000001
        result = get_telethon_entity_id(chat_id)
        assert result == 1

    def test_supergroup_positive(self):
        """supergroup: 正数chat_id（直接返回）"""
        chat_id = 1234567890
        result = get_telethon_entity_id(chat_id)
        assert result == 1234567890

    def test_group_negative(self):
        """普通group: 负数取绝对值"""
        chat_id = -1234567890
        result = get_telethon_entity_id(chat_id)
        assert result == 1234567890

    def test_private_chat(self):
        """私聊: 正数直接返回"""
        chat_id = 987654321
        result = get_telethon_entity_id(chat_id)
        assert result == 987654321

    def test_zero(self):
        """零值: 直接返回"""
        assert get_telethon_entity_id(0) == 0
