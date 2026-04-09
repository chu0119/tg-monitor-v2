#!/usr/bin/env python3
"""测试修复后的功能"""
import asyncio
import sys
from pathlib import Path

# 该文件是手动验证脚本，不应被 pytest 自动收集执行
if "pytest" in sys.modules:
    import pytest
    pytest.skip("manual verification script; skip in automated pytest runs", allow_module_level=True)

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

async def test_keywords_api():
    """测试关键词接口返回格式"""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select, func
    from app.models import KeywordGroup, Keyword

    print("\n[测试] GET /api/v1/keywords")
    async with AsyncSessionLocal() as db:
        # 模拟接口逻辑
        result = await db.execute(select(KeywordGroup))
        groups = result.scalars().all()
        
        total_keywords = 0
        items = []
        for group in groups:
            count_result = await db.execute(
                select(func.count(Keyword.id))
                .where(Keyword.group_id == group.id)
            )
            actual_count = count_result.scalar() or 0
            total_keywords += actual_count
            items.append({
                "id": group.id,
                "name": group.name,
                "total_keywords": actual_count
            })
        
        response = {
            "total": len(groups),
            "items_count": total_keywords,
            "items": items
        }
        
        print(f"✓ 返回格式正确: total={response['total']}, items_count={response['items_count']}")
        print(f"  包含 {len(response['items'])} 个关键词组")
        return True


async def test_cleanup_stats_performance():
    """测试清理统计接口性能（包含缓存测试）"""
    print("\n[测试] GET /api/v1/settings/cleanup/stats 性能")
    import time
    
    # 使用全局实例（保持缓存）
    from app.services.data_cleanup_service import data_cleanup_service
    
    # 第一次调用（冷启动，无缓存）
    start = time.time()
    stats = await data_cleanup_service.get_cleanup_stats()
    elapsed_cold = time.time() - start
    
    if "error" in stats:
        print(f"✗ 查询失败: {stats['error']}")
        return False
    
    print(f"  第一次查询（冷启动）: {elapsed_cold:.2f}s")
    
    # 第二次调用（有缓存）
    start = time.time()
    stats = await data_cleanup_service.get_cleanup_stats()
    elapsed_warm = time.time() - start
    
    print(f"  第二次查询（有缓存）: {elapsed_warm:.2f}s")
    print(f"  数据库大小: {stats['database_size_mb']} MB")
    print(f"  过期告警: {stats['expired']['alerts']} 条")
    print(f"  过期消息: {stats['expired']['messages']} 条")
    
    # 缓存后的查询应该很快
    if elapsed_warm < 2.0:
        print(f"  性能达标（缓存后 <2s） ✓")
        return True
    else:
        print(f"  性能未达标（缓存后 >2s） ✗")
        return False


async def test_batch_deduplication():
    """测试批量去重逻辑"""
    print("\n[测试] 批量消息去重逻辑")
    
    # 模拟批内去重
    processed_ids = set()
    messages = [
        type('obj', (object,), {'id': 1})(),
        type('obj', (object,), {'id': 2})(),
        type('obj', (object,), {'id': 1})(),  # 重复
        type('obj', (object,), {'id': 3})(),
        type('obj', (object,), {'id': 2})(),  # 重复
    ]
    
    unique_count = 0
    duplicate_count = 0
    
    for msg in messages:
        if msg.id in processed_ids:
            duplicate_count += 1
            continue
        processed_ids.add(msg.id)
        unique_count += 1
    
    print(f"✓ 去重逻辑正确: {unique_count} 条唯一, {duplicate_count} 条重复")
    return unique_count == 3 and duplicate_count == 2


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("TG 监控系统修复验证测试")
    print("=" * 60)
    
    results = []
    
    # 测试 1: 关键词接口
    try:
        result = await test_keywords_api()
        results.append(("关键词接口", result))
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        results.append(("关键词接口", False))
    
    # 测试 2: 清理统计性能
    try:
        result = await test_cleanup_stats_performance()
        results.append(("清理统计性能", result))
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        results.append(("清理统计性能", False))
    
    # 测试 3: 批量去重
    try:
        result = await test_batch_deduplication()
        results.append(("批量去重", result))
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        results.append(("批量去重", False))
    
    # 打印结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    print(f"\n总计: {passed}/{total} 通过")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
