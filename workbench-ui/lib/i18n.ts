export const languageCatalog = [
  { value: "en", label: "English", shortLabel: "EN", htmlLang: "en" },
  { value: "zh", label: "简体中文", shortLabel: "中文", htmlLang: "zh-CN" },
] as const;

export type Locale = (typeof languageCatalog)[number]["value"];

export function htmlLanguage(locale: Locale): string {
  return languageCatalog.find((item) => item.value === locale)?.htmlLang ?? "en";
}
