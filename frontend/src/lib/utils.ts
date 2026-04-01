import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 解析日期字符串为Date对象
 * 支持带时区信息的ISO格式和不带时区的旧格式
 */
function parseDate(date: string | Date): Date {
  if (date instanceof Date) {
    return date;
  }

  // 如果是字符串，检查时区信息
  // ISO 8601格式带时区: 2024-01-01T12:00:00+08:00 或 2024-01-01T12:00:00Z
  // 旧格式不带时区: 2024-01-01T12:00:00
  if (date.includes('+') || date.endsWith('Z')) {
    // 已有时区信息，直接解析（浏览器会自动转换为本地时区显示）
    return new Date(date);
  }

  // 后端发送的UTC时间不带时区后缀，添加'Z'将其解析为UTC时间
  // 浏览器会自动将UTC时间转换为本地时区显示
  return new Date(date + 'Z');
}

export function formatDate(date: string | Date): string {
  const d = parseDate(date);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export function formatRelativeTime(date: string | Date): string {
  const d = parseDate(date);
  const now = new Date();
  const diff = now.getTime() - d.getTime();

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    return `${days}天前`;
  } else if (hours > 0) {
    return `${hours}小时前`;
  } else if (minutes > 0) {
    return `${minutes}分钟前`;
  } else if (seconds > 0) {
    return `${seconds}秒前`;
  } else {
    return "刚刚";
  }
}

export function formatMessageTime(date: string | Date): string {
  const d = parseDate(date);
  const now = new Date();
  const diff = now.getTime() - d.getTime();

  // 如果消息在24小时内，显示相对时间
  if (diff < 24 * 60 * 60 * 1000) {
    return formatRelativeTime(date);
  }

  // 否则显示完整日期时间
  return formatDate(date);
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "...";
}
