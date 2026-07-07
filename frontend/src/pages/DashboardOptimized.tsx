/**
 * Dashboard优化说明
 * 
 * 当前优化策略：
 * 1. 使用React Query进行数据缓存
 * 2. 设置合理的staleTime减少重复请求
 * 3. 自动刷新间隔设置为30秒
 * 4. 禁用windowFocus时的自动刷新
 * 
 * 使用方法：
 * 将原来的fetchData调用替换为useDashboard hooks
 * 
 * 示例：
 * // 原来的代码
 * const [stats, setStats] = useState(null)
 * useEffect(() => {
 *   fetchData()
 *   interval = setInterval(fetchData, 30000)
 * }, [])
 * 
 * // 优化后的代码
 * import { useDashboardStats } from "../hooks/useDashboard"
 * const { data: stats, isLoading } = useDashboardStats()
 * 
 * 优势：
 * 1. 自动缓存，减少重复请求
 * 2. 自动重新验证数据新鲜度
 * 3. 支持后台刷新
 * 4. 内置加载状态和错误处理
 */

// 导出优化后的hooks
export { useDashboardStats, useKeywordTrend, useSenderRanking, useConversationActivity, useRecentAlerts } from "../hooks/useDashboard"
