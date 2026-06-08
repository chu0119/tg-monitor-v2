/* @refresh */
/* 此文件由 @tanstack/router 生成。编辑此文件将被覆盖。 */

import { createRoute } from "@tanstack/react-router"
import { createRootRoute } from "@tanstack/react-router"
import {
    DashboardPage,
} from "@/pages/DashboardPage"
import {
    MonitoringPage,
} from "@/pages/MonitoringPage"
import {
    AlertsPage,
} from "@/pages/AlertsPage"
import {
    KeywordsPage,
} from "@/pages/KeywordsPage"
import {
    ConversationsPage,
} from "@/pages/ConversationsPage"
import {
    NotificationsPage,
} from "@/pages/NotificationsPage"
import {
    AccountsPage,
} from "@/pages/AccountsPage"
import {
    SettingsPage,
} from "@/pages/SettingsPage"
import {
    BigScreenPage,
} from "@/pages/BigScreenPage"
import {
    ProxyPage,
} from "@/pages/ProxyPage"
import {
    SetupPage,
} from "@/pages/SetupPage"
import {
    AnalysisPage,
} from "@/pages/AnalysisPage"
import {
    MainLayout,
} from "@/components/layout/MainLayout"

const rootRoute = createRootRoute({
  component: MainLayout,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: DashboardPage,
})

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/dashboard",
  component: DashboardPage,
})

const monitoringRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/monitoring",
  component: MonitoringPage,
})

const alertsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/alerts",
  component: AlertsPage,
})

const keywordsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/keywords",
  component: KeywordsPage,
})

const conversationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/conversations",
  component: ConversationsPage,
})

const notificationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/notifications",
  component: NotificationsPage,
})

const accountsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/accounts",
  component: AccountsPage,
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsPage,
})

const bigscreenRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/bigscreen",
  component: BigScreenPage,
})

const proxyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/proxy",
  component: ProxyPage,
})

const setupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup",
  component: SetupPage,
})

const analysisRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/analysis",
  component: AnalysisPage,
})

export const routeTree = rootRoute.addChildren([
  indexRoute,
  dashboardRoute,
  monitoringRoute,
  alertsRoute,
  keywordsRoute,
  conversationsRoute,
  notificationsRoute,
  accountsRoute,
  settingsRoute,
  bigscreenRoute,
  proxyRoute,
  setupRoute,
  analysisRoute,
])
