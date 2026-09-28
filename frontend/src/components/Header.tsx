import React from 'react';
import {
  TrendingUp,
  Settings,
  RefreshCw,
  Database,
  ChevronRight,
  Sparkles
} from 'lucide-react';

interface HeaderProps {
  onOpenSettings: () => void;
  onOpenDataLake?: () => void;
  systemStatus: {
    status: string;
    total_bonds: number;
    benchmark: string;
    last_updated: string;
    data_lake?: {
      ready: boolean;
      cached_symbols: number;
      total_symbols: number;
      percentage: number;
    };
  } | null;
  onRefreshQuotes: () => void;
  refreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onOpenSettings,
  onOpenDataLake,
  systemStatus,
  onRefreshQuotes,
  refreshing,
}) => {
  return (
    <header className="bg-white/95 backdrop-blur-md border-b border-slate-200 sticky top-0 z-40 shadow-xs w-full">
      <div className="w-full px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand & Title */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-indigo-700 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base sm:text-lg text-slate-900 tracking-tight">
                A股可转债 AI 投研与多账号实盘终端
              </span>
              <span className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-[10px] font-black px-1.5 py-0.5 rounded tracking-wider uppercase shadow-2xs">
                PRO v2.5
              </span>
            </div>
            <p className="text-[11px] text-slate-500 hidden sm:block">
              策略工坊 ➔ 历史对决 ➔ 模拟赛马 ➔ 多账号管家 ➔ LangGraph 多智能体会诊
            </p>
          </div>
        </div>

        {/* Live Status & Optimized Capsules */}
        <div className="flex items-center gap-2.5">
          <div className="hidden lg:flex items-center gap-2.5">
            {/* 胶囊 1: 实时行情在线 */}
            <div
              className="flex items-center gap-2 bg-emerald-50/90 hover:bg-emerald-100/70 border border-emerald-200/90 text-emerald-800 px-3 py-1.5 rounded-full text-xs font-medium transition-all shadow-2xs cursor-default select-none"
              title="实时全市场可转债/ETF行情接入中，自动每日收盘估值"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="font-semibold text-slate-800">行情在线</span>
              <span className="font-mono text-[11px] font-bold text-emerald-700 bg-white/90 border border-emerald-200/60 px-1.5 py-0.2 rounded-full">
                {systemStatus?.total_bonds || 1059}只
              </span>
            </div>

            {/* 胶囊 2: 多资产数据湖（顶级主入口） */}
            <button
              onClick={onOpenDataLake}
              className="flex items-center gap-2 bg-gradient-to-r from-blue-50/90 via-indigo-50/80 to-purple-50/70 hover:from-blue-100 hover:via-indigo-100 hover:to-purple-100 border border-blue-200/90 hover:border-indigo-400 text-slate-800 px-3 py-1.5 rounded-full text-xs transition-all shadow-2xs hover:shadow-xs cursor-pointer group select-none"
              title="点击打开本地多资产数据湖可视化管理中枢（可转债 / ETF / A股 / 美股 / 指数）"
            >
              <span className="w-5 h-5 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 text-white flex items-center justify-center text-[10px] group-hover:scale-110 transition-transform shadow-2xs">
                <Database className="w-3 h-3" />
              </span>
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-slate-900 group-hover:text-indigo-700 transition-colors">
                  多资产数据湖
                </span>
                <span className="text-[11px] font-mono text-indigo-700 bg-white/95 border border-indigo-200/70 px-1.5 py-0.2 rounded-md font-semibold">
                  82.5万条 · 5类资产
                </span>
              </div>
              <span className="text-[10px] bg-indigo-600 group-hover:bg-indigo-700 text-white font-bold px-1.5 py-0.5 rounded-full transition-colors flex items-center gap-0.5 shadow-2xs">
                <span>管理</span>
                <ChevronRight className="w-2.5 h-2.5 group-hover:translate-x-0.5 transition-transform" />
              </span>
            </button>
          </div>

          {/* 刷新行情估值按钮 */}
          <button
            onClick={onRefreshQuotes}
            disabled={refreshing}
            className="p-2 text-slate-500 hover:text-blue-600 hover:bg-slate-100 rounded-xl transition-all border border-transparent hover:border-slate-200 cursor-pointer"
            title="刷新行情估值与系统状态"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-blue-600' : ''}`} />
          </button>

          {/* 全局设置按钮 */}
          <button
            onClick={onOpenSettings}
            className="flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold px-3.5 py-2 rounded-xl shadow-xs hover:shadow transition-all cursor-pointer"
          >
            <Settings className="w-3.5 h-3.5" />
            <span>全局设置</span>
          </button>
        </div>
      </div>
    </header>
  );
};
