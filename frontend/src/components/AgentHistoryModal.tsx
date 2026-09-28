import React, { useState, useEffect } from 'react';
import { AgentReportSummary, AgentResult } from '../types';
import { api } from '../api/client';
import {
  X,
  History,
  Scale,
  MessageSquare,
  Trash2,
  Eye,
  Calendar,
  Layers,
  Sparkles,
  ChevronRight,
  Loader2,
  Clock
} from 'lucide-react';

interface AgentHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectReport: (report: AgentResult) => void;
}

export const AgentHistoryModal: React.FC<AgentHistoryModalProps> = ({
  isOpen,
  onClose,
  onSelectReport,
}) => {
  const [historyList, setHistoryList] = useState<AgentReportSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingDetailId, setLoadingDetailId] = useState<string | null>(null);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const data = await api.getAgentReportsHistory();
      if (Array.isArray(data)) {
        setHistoryList(data);
      }
    } catch (e) {
      console.error('Failed to load reports history', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchHistory();
    }
  }, [isOpen]);

  const handleSelect = async (id: string) => {
    setLoadingDetailId(id);
    try {
      const detail = await api.getAgentReportDetail(id);
      onSelectReport(detail);
      onClose();
    } catch (e: any) {
      alert(`调取报告失败: ${e.message}`);
    } finally {
      setLoadingDetailId(null);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('确定要删除本期历史会审记录吗？')) return;
    try {
      await api.deleteAgentReport(id);
      setHistoryList((prev) => prev.filter((r) => r.id !== id));
    } catch (e: any) {
      alert(`删除失败: ${e.message}`);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white w-full max-w-3xl rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-xs">
              <History className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <span>历史投研会审与裁决档案库</span>
                <span className="text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.2 rounded-full">
                  已永久安全归档 {historyList.length} 期
                </span>
              </h3>
              <p className="text-xs text-slate-500">
                支持调取历史各期量化初筛、专家辩论实录、法官判词与建议权重，复盘验证决策胜率。
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-400 space-y-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
              <span className="text-xs">加载历史归档记录中...</span>
            </div>
          ) : historyList.length === 0 ? (
            <div className="py-16 text-center space-y-2 text-slate-400">
              <History className="w-10 h-10 mx-auto opacity-40 text-slate-400" />
              <p className="text-xs font-medium text-slate-600">暂无历史归档记录</p>
              <p className="text-[11px] text-slate-400">
                每次点击“召开会诊”或“开启法庭裁决”后，系统都会自动为您完整保留该期全量发言与组合。
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {historyList.map((item) => {
                const isCourt = item.chamber_type === 'COURTROOM';
                const isSelecting = loadingDetailId === item.id;
                return (
                  <div
                    key={item.id}
                    onClick={() => handleSelect(item.id)}
                    className="p-3.5 rounded-xl border border-slate-200 bg-white hover:border-indigo-300 hover:shadow-xs transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 group"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border flex items-center gap-1 ${
                          isCourt
                            ? 'bg-amber-50 text-amber-800 border-amber-200'
                            : 'bg-blue-50 text-blue-700 border-blue-200'
                        }`}>
                          {isCourt ? <Scale className="w-3 h-3 text-amber-600" /> : <MessageSquare className="w-3 h-3 text-blue-600" />}
                          <span>{item.chamber_name}</span>
                        </span>

                        <span className="font-bold text-xs text-slate-900">
                          {item.strategy_name}
                        </span>

                        <span className="text-[11px] text-slate-400 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          <span>{item.run_time || item.created_at}</span>
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-500 flex items-center gap-2">
                        <span>初筛入围: <b className="text-blue-600 font-semibold">{item.candidates_count}</b> 只</span>
                        <span className="text-slate-300">•</span>
                        <span>排雷拦截: <b className="text-rose-600 font-semibold">{item.vetoed_count}</b> 只</span>
                        <span className="text-slate-300">•</span>
                        <span>最终配置: <b className="text-emerald-600 font-semibold">{item.portfolio_count}</b> 只</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                      <button
                        onClick={(e) => handleDelete(item.id, e)}
                        className="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg hover:bg-rose-50 transition-colors cursor-pointer"
                        title="删除本条历史归档"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>

                      <button
                        disabled={isSelecting}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-700 group-hover:bg-indigo-600 group-hover:text-white transition-all shadow-2xs"
                      >
                        {isSelecting ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Eye className="w-3.5 h-3.5" />
                        )}
                        <span>调取查阅</span>
                        <ChevronRight className="w-3 h-3 ml-0.5 opacity-60" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
          <span>提示：调取后历史报告将在主工作区以只读归档模式展示，随时可点击退出并开启全新会审。</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-medium rounded-lg transition-colors cursor-pointer"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
};
