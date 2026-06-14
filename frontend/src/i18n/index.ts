/**
 * i18n 国际化配置
 */
import { en } from "./en";
import { zh } from "./zh";

export type Language = "en" | "zh";
export type Translations = typeof en;

// 语言包
export const languages = {
  en,
  zh,
} as const;

// 当前语言
let currentLanguage: Language = "zh";

/**
 * 设置当前语言
 */
export function setLanguage(lang: Language) {
  currentLanguage = lang;
  if (typeof window !== "undefined") {
    localStorage.setItem("language", lang);
  }
}

/**
 * 获取当前语言
 */
export function getLanguage(): Language {
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem("language") as Language;
    if (stored && (stored === "en" || stored === "zh")) {
      return stored;
    }
  }
  return currentLanguage;
}

/**
 * 翻译函数
 */
export function t(key: string, params?: Record<string, string | number>): string {
  const lang = getLanguage();
  const translations = languages[lang];

  // 支持嵌套路径，如 "common.loading"
  const keys = key.split(".");
  let value: any = translations;

  for (const k of keys) {
    if (value && typeof value === "object" && k in value) {
      value = value[k];
    } else {
      // 找不到翻译，返回 key
      return key;
    }
  }

  if (typeof value !== "string") {
    return key;
  }

  // 支持参数替换，如 "共 {total} 条"
  if (params) {
    return value.replace(/\{(\w+)\}/g, (_, paramKey) => {
      return params[paramKey]?.toString() || `{${paramKey}}`;
    });
  }

  return value;
}

/**
 * 创建翻译 Hook (用于 React 组件)
 */
export function useTranslation() {
  const language = getLanguage();

  return {
    language,
    t: (key: string, params?: Record<string, string | number>) => t(key, params),
    setLanguage,
  };
}
