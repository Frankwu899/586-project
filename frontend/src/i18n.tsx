import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { ApiError, request } from './api';
import { interfaceChinese } from './i18nCatalog';

export type AppLanguage = 'English' | 'Chinese';
export type TranslationValues = Record<string, string | number>;
export type Translate = (english: string, values?: TranslationValues) => string;
const translations: Record<string, string> = {
  ...interfaceChinese,
  Open: '打开', Close: '关闭', Save: '保存', Delete: '删除', Cancel: '取消', Continue: '继续',
  Edit: '编辑', Remove: '移除', Confirm: '确认', Retry: '重试', 'Try again': '重试',
  'Not provided': '未提供', 'Not analyzed': '尚未分析', 'Loading…': '正在加载…', 'Saving…': '正在保存…',
  'English': 'English', 'Chinese': '中文', 'Research': '研究', 'Ideas': '创意', 'Production': '制作',
  'Timeline': '时间线', 'Structure': '结构', 'Project context': '项目背景', 'Projects': '项目',
  'New project': '新建项目', 'Project name': '项目名称', 'API connection': 'API 连接',
};

/** Only pass application-authored interface text, never source quotes or saved model output. */
export function registerTranslations(entries: Record<string, string>) {
  Object.assign(translations, entries);
}
export function translate(language: AppLanguage, english: string, values?: TranslationValues): string {
  const text = language === 'Chinese' ? translations[english] ?? english : english;
  return values ? text.replace(/\{(\w+)\}/g, (match, key: string) => values[key] === undefined ? match : String(values[key])) : text;
}

interface I18nContextValue { language: AppLanguage; setLanguage: (language: AppLanguage) => Promise<void>; t: Translate }
const storageKey = 'video-anatomy:app-language';
function rememberedLanguage(): AppLanguage {
  try { return localStorage.getItem(storageKey) === 'Chinese' ? 'Chinese' : 'English'; } catch { return 'English'; }
}
function remember(language: AppLanguage) {
  try { localStorage.setItem(storageKey, language); } catch { /* Language remains usable in private browsing. */ }
}
const I18nContext = createContext<I18nContextValue>({ language: 'English', setLanguage: async () => {}, t: (english, values) => translate('English', english, values) });
export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, updateLanguage] = useState<AppLanguage>(rememberedLanguage);
  const revision = useRef(0);
  useEffect(() => {
    let active = true;
    const started = revision.current;
    void request<{ language: AppLanguage }>('/local/preferences').then((value) => {
      if (active && revision.current === started && ['English', 'Chinese'].includes(value.language)) {
        updateLanguage(value.language); remember(value.language);
      }
    }).catch(() => { /* Development APIs without local preferences retain this browser's UI preference. */ });
    return () => { active = false; };
  }, []);
  const setLanguage = useCallback(async (next: AppLanguage) => {
    const current = ++revision.current;
    try {
      await request<{ language: AppLanguage }>('/local/preferences', { language: next });
    } catch (failure) {
      // A real server failure must not silently leave research using another language.
      if (!(failure instanceof ApiError) || ![404, 405].includes(failure.status)) throw failure;
    }
    if (revision.current === current) { updateLanguage(next); remember(next); }
  }, []);
  const t = useCallback<Translate>((english, values) => translate(language, english, values), [language]);
  useEffect(() => { document.documentElement.lang = language === 'Chinese' ? 'zh-CN' : 'en'; }, [language]);
  return <I18nContext.Provider value={{ language, setLanguage, t }}>{children}</I18nContext.Provider>;
}
export const useI18n = () => useContext(I18nContext);
