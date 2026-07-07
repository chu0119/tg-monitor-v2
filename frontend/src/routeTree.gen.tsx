import React, { Suspense } from "react";
/* @refresh */
/* 此文件由 @tanstack/router 生成。编辑此文件将被覆盖。 */

import { createRoute } from "@tanstack/react-router"
import { createRootRoute } from "@tanstack/react-router"
import { MainLayout } from "@/components/layout/MainLayout"

// Lazy loaded pages
const LazyDashboardPage = React.lazy(() => import("@/pages/DashboardPage").then(m => ({ default: m.DashboardPage || m.default })));
const LazyMonitoringPage = React.lazy(() => import("@/pages/MonitoringPage").then(m => ({ default: m.MonitoringPage || m.default })));
const LazyAlertsPage = React.lazy(() => import("@/pages/AlertsPage").then(m => ({ default: m.AlertsPage || m.default })));
const LazyPhoneIntelPage = React.lazy(() => import("@/pages/PhoneIntelPage").then(m => ({ default: m.PhoneIntelPage || m.default })));
const LazyPersonnelPage = React.lazy(() => import("@/routes/personnel").then(m => ({ default: m.PersonnelComponent || m.default })));
const LazyProxyPage = React.lazy(() => import("@/pages/ProxyPage").then(m => ({ default: m.ProxyPage || m.default })));
const LazyKeywordsPage = React.lazy(() => import("@/pages/KeywordsPage").then(m => ({ default: m.KeywordsPage || m.default })));
const LazyConversationsPage = React.lazy(() => import("@/pages/ConversationsPage").then(m => ({ default: m.ConversationsPage || m.default })));
const LazyNotificationsPage = React.lazy(() => import("@/pages/NotificationsPage").then(m => ({ default: m.NotificationsPage || m.default })));
const LazyAccountsPage = React.lazy(() => import("@/pages/AccountsPage").then(m => ({ default: m.AccountsPage || m.default })));
const LazySettingsPage = React.lazy(() => import("@/pages/SettingsPage").then(m => ({ default: m.SettingsPage || m.default })));
const LazyBigScreenPage = React.lazy(() => import("@/pages/BigScreenPage").then(m => ({ default: m.BigScreenPage || m.default })));
const LazyAnalysisPage = React.lazy(() => import("@/pages/AnalysisPage").then(m => ({ default: m.AnalysisPage || m.default })));
const LazyCasesPage = React.lazy(() => import("@/pages/CasesPage").then(m => ({ default: m.CasesPage || m.default })));
const LazyWatchlistPage = React.lazy(() => import("@/pages/WatchlistPage").then(m => ({ default: m.WatchlistPage || m.default })));
const LazyAuditPage = React.lazy(() => import("@/pages/AuditPage").then(m => ({ default: m.AuditPage || m.default })));

// Loading fallback
function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-screen bg-gray-900">
      <div className="text-gray-400 text-lg">加载中...</div>
    </div>
  );
}

const rootRoute = createRootRoute({
  component: () => (
    <Suspense fallback={<LoadingFallback />}>
      <MainLayout />
    </Suspense>
  ),
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: LazyDashboardPage,
})

const monitoringRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/monitoring",
  component: LazyMonitoringPage,
})

const alertsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/alerts",
  component: LazyAlertsPage,
})

const phoneIntelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/phone-intel",
  component: LazyPhoneIntelPage,
})

const personnelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/personnel",
  component: LazyPersonnelPage,
})

const proxyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/proxy",
  component: LazyProxyPage,
})

const keywordsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/keywords",
  component: LazyKeywordsPage,
})

const conversationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/conversations",
  component: LazyConversationsPage,
})

const notificationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/notifications",
  component: LazyNotificationsPage,
})

const accountsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/accounts",
  component: LazyAccountsPage,
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: LazySettingsPage,
})

const bigscreenRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/bigscreen",
  component: LazyBigScreenPage,
})

const analysisRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/analysis",
  component: LazyAnalysisPage,
})

const casesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/cases",
  component: LazyCasesPage,
})

const watchlistRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/watchlist",
  component: LazyWatchlistPage,
})

const auditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/audit",
  component: LazyAuditPage,
})

export const routeTree = rootRoute.addChildren([
  indexRoute,
  monitoringRoute,
  alertsRoute,
  phoneIntelRoute,
  personnelRoute,
  proxyRoute,
  keywordsRoute,
  conversationsRoute,
  notificationsRoute,
  accountsRoute,
  settingsRoute,
  bigscreenRoute,
  analysisRoute,
  casesRoute,
  watchlistRoute,
  auditRoute,
])
