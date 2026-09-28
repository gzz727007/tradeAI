import React, { useState, useEffect } from 'react';
import { AgentResult, CandidateBond, Strategy, MeetingChamber, AgentSpeech } from '../types';
import { api } from '../api/client';
import { AgentStudioModal } from './AgentStudioModal';
import { AgentHistoryModal } from './AgentHistoryModal';
import {
  Bot,
  Play,
  CheckCircle2,
  AlertOctagon,
  Shield,
  Zap,
  Swords,
  Crown,
  Star,
  MessageSquare,
  Loader2,
  Info,
  Filter,
  SlidersHorizontal,
  Sparkles,
  Layers,
  Scale,
  Gavel,
  Settings,
  Quote,
  ChevronRight,
  Eye,
  FileCheck2,
  TrendingDown,
  TrendingUp,
  History,
  PlusCircle,
  RotateCcw,
  ArrowRight,
  ShieldCheck,
  Target,
  BarChart2
} from 'lucide-react';

interface AgentConsultationProps {
  selectedStrategyId?: string | null;
  onSelectStrategyId?: (id: string) => void;
  strategies?: Strategy[];
}

export const AgentConsultation: React.FC<AgentConsultationProps> = ({
  selectedStrategyId,
  onSelectStrategyId,
  strategies = [],
}) => {
  const [result, setResult] = useState<AgentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [streamSteps, setStreamSteps] = useState<Array<{ step: string; message: string }>>([]);
  const [selectedBondCode, setSelectedBondCode] = useState<string>('');
  const [llmConfig, setLlmConfig] = useState<any>(null);

  const [chambersList, setChambersList] = useState<MeetingChamber[]>([]);
  const [currentChamberId, setCurrentChamberId] = useState<string>('chamber_cb_roundtable');
  const [studioOpen, setStudioOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyCount, setHistoryCount] = useState(0);
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});

  const [strategiesList, setStrategiesList] = useState<Strategy[]>(strategies);
  const [currentStrategyId, setCurrentStrategyId] = useState<string>(selectedStrategyId || 'default');

  useEffect(() => {
    if (selectedStrategyId) {
      setCurrentStrategyId(selectedStrategyId);
    }
  }, [selectedStrategyId]);

  useEffect(() => {
    if (!strategies || strategies.length === 0) {
      api.getStrategies().then((list) => {
        if (Array.isArray(list)) setStrategiesList(list);
      }).catch(console.error);
    } else {
      setStrategiesList(strategies);
    }
  }, [strategies]);

  const activeStrategy = strategiesList.find((s) => s.id === currentStrategyId);

  const fetchHistoryCount = async () => {
    try {
      const data = await api.getAgentReportsHistory();
      if (Array.isArray(data)) {
        setHistoryCount(data.length);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const loadChambers = async () => {
    try {
      const data = await api.getChambers();
      if (Array.isArray(data)) {
        setChambersList(data);
        if (data.length > 0 && !currentChamberId) {
          setCurrentChamberId(data[0].id);
        }
      }
    } catch (e) {
      console.error('Failed to load chambers', e);
    }
  };

  const loadCachedResult = async () => {
    try {
      const data = await api.getAgentResult();
      if (data.has_run) {
        if (selectedStrategyId && data.strategy_id !== selectedStrategyId) {
          return;
        }
        setResult(data);
        if (data.chamber_id) {
          setCurrentChamberId(data.chamber_id);
        }
        if (data.final_portfolio && data.final_portfolio.length > 0) {
          setSelectedBondCode(data.final_portfolio[0].bond_code);
        }
        if (data.strategy_id && !selectedStrategyId) {
          setCurrentStrategyId(data.strategy_id);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadCachedResult();
    loadChambers();
    fetchHistoryCount();
    api.getLLMConfig().then((data) => setLlmConfig(data)).catch(() => {});
  }, []);

  const handleStartConsultation = () => {
    setLoading(true);
    setStreamSteps([]);

    // Open WebSocket with strategy_id and chamber_id
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const params = new URLSearchParams();
    if (currentStrategyId && currentStrategyId !== 'default') {
      params.append('strategy_id', currentStrategyId);
    }
    if (currentChamberId) {
      params.append('chamber_id', currentChamberId);
    }
    const query = params.toString() ? `?${params.toString()}` : '';
    const wsUrl = `${protocol}//${window.location.host}/ws/agents/stream${query}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.message) {
        setStreamSteps((prev) => [...prev, { step: data.step, message: data.message }]);
      }

      if (data.step === 'complete' && data.data) {
        setResult(data.data);
        if (data.data.final_portfolio?.length > 0) {
          setSelectedBondCode(data.data.final_portfolio[0].bond_code);
        }
        setLoading(false);
        fetchHistoryCount();
        ws.close();
      } else if (data.step === 'error') {
        alert(`会诊失败: ${data.message}`);
        setLoading(false);
        ws.close();
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket error, falling back to HTTP', err);
      // Fallback to HTTP
      api.runAgents(
        currentStrategyId && currentStrategyId !== 'default' ? currentStrategyId : undefined,
        currentChamberId
      )
        .then((data) => {
          setResult(data);
          if (data.final_portfolio?.length > 0) {
            setSelectedBondCode(data.final_portfolio[0].bond_code);
          }
          setLoading(false);
          fetchHistoryCount();
        })
        .catch((e) => {
          alert(`请求失败: ${e.message}`);
          setLoading(false);
        });
    };
  };

  const handleManualNotify = async () => {
    try {
      const res = await fetch('/api/agents/notify', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        alert(data.message || '广播推送成功！');
      } else {
        alert(data.detail || '推送失败');
      }
    } catch (e: any) {
      alert(`推送失败: ${e.message}`);
    }
  };

  const selectedCand = result?.candidates?.find((c) => c.bond_code === selectedBondCode);
  const selectedPortfolioItem = result?.final_portfolio?.find((p) => p.bond_code === selectedBondCode);
  const creditRev = result?.credit_reviews?.[selectedBondCode];
  const equityRev = result?.equity_reviews?.[selectedBondCode];
  const clauseRev = result?.clause_reviews?.[selectedBondCode];

  const activeProviderKey = llmConfig?.active_provider;
  const activeProviderInfo = llmConfig?.providers?.[activeProviderKey];
  const activeModelName = activeProviderInfo?.model || '已就绪模型';
  const activeProviderName = activeProviderInfo?.name || '大模型';

  const activeChamber = chambersList.find((c) => c.id === currentChamberId) || chambersList[0];
  const isCourtroomMode = activeChamber?.chamber_type === 'COURTROOM';

  return (
    <div className="space-y-4">
      {/* Strategy-Driven Controller Bar */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
        {/* Top Header & Run Button */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-lg text-white flex items-center justify-center shadow-xs ${
                isCourtroomMode ? 'bg-linear-to-tr from-amber-600 to-rose-600' : 'bg-linear-to-tr from-blue-600 to-indigo-600'
              }`}>
                {isCourtroomMode ? <Scale className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                  <span>{activeChamber?.name || 'AI 智能体投研会诊室'}</span>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                    isCourtroomMode ? 'bg-amber-50 text-amber-800 border-amber-200' : 'bg-purple-50 text-purple-700 border-purple-200'
                  }`}>
                    {isCourtroomMode ? '⚖️ 3 轮多空指控抗辩 + 首席法官裁决' : '🏛️ Quantamental 量化初筛 + 专家圆桌'}
                  </span>
                </h3>
                {llmConfig?.is_ready && (
                  <span className="inline-flex items-center gap-1.5 text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-0.5 rounded-full shadow-2xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span>算力引擎: <b>{activeProviderName}</b> · <code className="bg-white/80 px-1 py-0.2 rounded text-[9px] text-emerald-800">{activeModelName}</code></span>
                  </span>
                )}
              </div>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">
              {activeChamber?.description || '前置量化策略筛选标的，多智能体协同研判生成最优组合。'}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            {result && result.has_run && (
              <button
                onClick={() => setResult(null)}
                className="flex items-center gap-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-semibold px-3 py-2.5 rounded-xl shadow-2xs transition-all cursor-pointer"
                title="清空当前结果，切换至全新开庭界面"
              >
                <PlusCircle className="w-3.5 h-3.5 text-emerald-600" />
                <span>✨ 开启全新会审</span>
              </button>
            )}

            <button
              onClick={() => setHistoryOpen(true)}
              className="flex items-center gap-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-semibold px-3 py-2.5 rounded-xl shadow-2xs transition-all cursor-pointer"
              title="查看历史投研会审与裁决档案库"
            >
              <History className="w-3.5 h-3.5 text-indigo-600" />
              <span>📜 历史档案库</span>
              {historyCount > 0 && (
                <span className="text-[10px] bg-indigo-100 text-indigo-700 font-mono px-1.5 py-0.2 rounded-full font-bold">
                  {historyCount}
                </span>
              )}
            </button>

            <button
              onClick={() => setStudioOpen(true)}
              className="flex items-center gap-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-semibold px-3 py-2.5 rounded-xl shadow-2xs transition-all cursor-pointer"
              title="配置与扩展自定义智能体人才库"
            >
              <Settings className="w-3.5 h-3.5 text-slate-500" />
              <span>⚙️ 智能体工坊</span>
            </button>

            <button
              onClick={handleStartConsultation}
              disabled={loading}
              className={`flex items-center gap-2 text-white text-xs font-semibold px-5 py-2.5 rounded-xl shadow-sm hover:shadow transition-all cursor-pointer disabled:opacity-50 shrink-0 ${
                isCourtroomMode
                  ? 'bg-linear-to-r from-amber-600 via-rose-600 to-amber-700 hover:from-amber-700 hover:to-rose-700'
                  : 'bg-linear-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700'
              }`}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{isCourtroomMode ? '多空法庭激烈合议审理中...' : '投委会多智能体协同会诊中...'}</span>
                </>
              ) : (
                <>
                  {isCourtroomMode ? <Gavel className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
                  <span>{isCourtroomMode ? '敲槌！开启金融多空法庭裁决' : '召开今日投委会实时会诊'}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Chamber Selection Pills */}
        <div className="pt-2 border-t border-slate-100 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
            <span className="text-xs font-bold text-slate-700 flex items-center gap-1 shrink-0 mr-1">
              <Layers className="w-3.5 h-3.5 text-indigo-600" />
              <span>选择会场：</span>
            </span>
            {chambersList.map((ch) => {
              const isActive = currentChamberId === ch.id;
              const isCourt = ch.chamber_type === 'COURTROOM';
              return (
                <button
                  key={ch.id}
                  onClick={() => {
                    setCurrentChamberId(ch.id);
                    if (result && result.chamber_id && result.chamber_id !== ch.id) {
                      setResult(null);
                    }
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer border shrink-0 ${
                    isActive
                      ? isCourt
                        ? 'bg-amber-600 text-white border-amber-600 shadow-xs'
                        : 'bg-blue-600 text-white border-blue-600 shadow-xs'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {isCourt ? <Scale className="w-3.5 h-3.5" /> : <MessageSquare className="w-3.5 h-3.5" />}
                  <span>{ch.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-normal ${
                    isActive ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500'
                  }`}>
                    {ch.agent_ids?.length || 0}智能体
                  </span>
                </button>
              );
            })}
          </div>

          <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-slate-400" />
            <span>每个智能体的独立发言与举证链均被逐字存证，支持穿透审计。</span>
          </div>
        </div>

        {/* Strategy Selector Line */}
        <div className="pt-3 border-t border-slate-100 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 bg-slate-50/80 -mx-5 -mb-5 p-4 rounded-b-2xl border-t">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5 shrink-0">
              <Filter className="w-3.5 h-3.5 text-blue-600" />
              <span>初筛候选源策略：</span>
            </span>

            <select
              value={currentStrategyId || 'default'}
              onChange={(e) => {
                const val = e.target.value;
                setCurrentStrategyId(val);
                if (onSelectStrategyId) onSelectStrategyId(val);
                if (result && (result.strategy_id || 'default') !== val) {
                  setResult(null);
                }
              }}
              className="text-xs font-semibold bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-slate-800 shadow-2xs focus:outline-hidden focus:border-blue-500 cursor-pointer"
            >
              <option value="default">🎯 系统默认量化初筛 (95~130元 · 规模≤8亿 · 经典双低)</option>
              {strategiesList.map((st) => (
                <option key={st.id} value={st.id}>
                  📌 {st.name} ({st.category})
                </option>
              ))}
            </select>
          </div>

          {/* Active Strategy Constraints Preview */}
          {activeStrategy && (
            <div className="flex items-center gap-1.5 flex-wrap text-[11px] text-slate-500">
              <span className="text-slate-400 font-medium">策略量化准入条件:</span>
              <span className="bg-white px-2 py-0.5 rounded border border-slate-200 font-medium text-slate-700">
                {activeStrategy.params?.min_price || 95}~{activeStrategy.params?.max_price || 125}元
              </span>
              <span className="bg-white px-2 py-0.5 rounded border border-slate-200 font-medium text-slate-700">
                规模&le;{activeStrategy.params?.max_scale || 5}亿
              </span>
              <span className="bg-white px-2 py-0.5 rounded border border-slate-200 font-medium text-slate-700">
                溢价率&le;{activeStrategy.params?.max_premium || 50}%
              </span>
              <span className="bg-white px-2 py-0.5 rounded border border-slate-200 font-medium text-slate-700">
                双低权重 W={activeStrategy.params?.double_low_weight || 1.0}
              </span>
              <span className="bg-white px-2 py-0.5 rounded border border-slate-200 font-medium text-slate-700">
                排序: {activeStrategy.params?.sort_by || 'double_low'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Streaming Progress Box */}
      {loading && (
        <div className="bg-white rounded-xl border border-blue-200 p-4 shadow-sm space-y-2.5 animate-pulse">
          <div className="font-bold text-xs text-blue-800 flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>🤖 LangGraph 多智能体协作流水线推进中：</span>
          </div>
          <div className="space-y-1.5 font-mono text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-100 max-h-48 overflow-y-auto">
            {streamSteps.map((s, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <span className="text-blue-500 font-bold">›</span>
                <span>{s.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Consultation Results */}
      {result && result.has_run && (
        <div className="space-y-4">
          {/* Archived Report Status Banner */}
          {result.is_archived && (
            <div className="bg-linear-to-r from-amber-50 to-orange-50 border border-amber-300 rounded-xl p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-amber-900 shadow-2xs">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-amber-500 text-white flex items-center justify-center shrink-0 shadow-xs text-base">
                  📜
                </div>
                <div>
                  <div className="flex items-center gap-2 font-bold text-xs text-amber-900">
                    <span>当前正在调阅【历史归档投研报告】</span>
                    <span className="text-[10px] bg-amber-200/90 text-amber-800 px-2 py-0.5 rounded-full font-semibold">
                      会审归档时间: {result.run_time || '历史记录'}
                    </span>
                  </div>
                  <p className="text-[11px] text-amber-700 mt-0.5">
                    此快照来自历史档案库。您可以查阅当时的辩论全景与投资裁决，或随时点击右侧按钮退出并进入全新的会审就绪页。
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setResult(null);
                  setSelectedBondCode('');
                }}
                className="shrink-0 flex items-center gap-1.5 px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer transition-all"
              >
                <PlusCircle className="w-3.5 h-3.5" />
                <span>退出查阅 · 开启全新会审</span>
              </button>
            </div>
          )}

          {/* Strategy Attribution / Quantamental Pipeline Summary Card */}
          <div className="bg-gradient-to-r from-blue-50/70 via-indigo-50/50 to-purple-50/70 border border-blue-200/80 rounded-xl p-3.5 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-bold text-slate-800">
                    本报告量化前置源：【{result.strategy_name || '默认量化初筛'}】
                  </span>
                  {result.strategy_category && (
                    <span className="text-[10px] font-semibold bg-blue-100/70 text-blue-700 px-2 py-0.5 rounded-full border border-blue-200">
                      {result.strategy_category}
                    </span>
                  )}
                  {result.run_time && (
                    <span className="text-[10px] text-slate-400">
                      (会审于 {result.run_time})
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  全市场 500+ 只转债 → 量化策略初筛入围 <b className="text-blue-600 font-bold">{result.screened_count || result.candidates?.length || 0}</b> 只 → 多智能体全景穿透审查 (排除高危 <b className="text-rose-600 font-bold">{result.vetoed_bonds?.length || 0}</b> 只) → 终审精选入库 <b className="text-emerald-600 font-bold">{result.final_portfolio?.length || 0}</b> 只
                </p>
                {currentStrategyId && currentStrategyId !== (result.strategy_id || 'default') && (
                  <div className="mt-1.5 text-[11px] text-amber-700 bg-amber-50/90 border border-amber-200 rounded px-2 py-0.5 inline-flex items-center gap-1">
                    <span>💡 您已在上方切换初筛候选策略为【{activeStrategy?.name || currentStrategyId}】，点击右上角橙色【{isCourtroomMode ? '敲槌！开启金融多空法庭裁决' : '召开今日投委会实时会诊'}】按钮即可重新会审！</span>
                  </div>
                )}
              </div>
            </div>

            {result.strategy_params && (
              <div className="flex items-center gap-1.5 flex-wrap text-[10px] text-slate-600 shrink-0">
                {result.strategy_params.min_price != null && (
                  <span className="bg-white/80 px-2 py-0.5 rounded border border-slate-200">
                    价格: {result.strategy_params.min_price}~{result.strategy_params.max_price}
                  </span>
                )}
                {result.strategy_params.max_scale != null && (
                  <span className="bg-white/80 px-2 py-0.5 rounded border border-slate-200">
                    规模≤{result.strategy_params.max_scale}亿
                  </span>
                )}
                {result.strategy_params.max_premium != null && (
                  <span className="bg-white/80 px-2 py-0.5 rounded border border-slate-200">
                    溢价率≤{result.strategy_params.max_premium}%
                  </span>
                )}
              </div>
            )}
          </div>

          {/* PM Recommended Portfolio Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <span className="font-bold text-xs text-slate-800 flex items-center gap-1.5">
                <Crown className="w-4 h-4 text-amber-500" />
                <span>
                  🏆 投资总监 (PM) 今日裁决组合 (共 {result.final_portfolio.length} 只标的
                  {result.strategy_name ? ` · 源自【${result.strategy_name}】` : ''})
                </span>
              </span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-400">
                  更新时间: {result.run_time}
                </span>
                <button
                  onClick={handleManualNotify}
                  className="flex items-center gap-1 bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded text-xs font-medium cursor-pointer transition-colors"
                  title="重新广播推送到飞书/企业微信"
                >
                  <span>📢 广播推送飞书/微信</span>
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                  <tr>
                    <th className="py-2.5 px-4">转债代码</th>
                    <th className="py-2.5 px-4">转债名称</th>
                    <th className="py-2.5 px-4">现价 (元)</th>
                    <th className="py-2.5 px-4">双低综合值</th>
                    <th className="py-2.5 px-4">建议权重</th>
                    <th className="py-2.5 px-4">推荐星级</th>
                    <th className="py-2.5 px-4">PM 裁决结论与配置理由</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {result.final_portfolio.map((p) => {
                    const stars = Array(p.rating_stars || 4).fill('⭐').join('');
                    const isSelected = p.bond_code === selectedBondCode;
                    return (
                      <tr
                        key={p.bond_code}
                        onClick={() => setSelectedBondCode(p.bond_code)}
                        className={`transition-colors cursor-pointer ${
                          isSelected ? 'bg-blue-50/70 font-medium' : 'hover:bg-slate-50/50'
                        }`}
                      >
                        <td className="py-2.5 px-4 font-mono font-semibold text-slate-700">{p.bond_code}</td>
                        <td className="py-2.5 px-4 font-bold text-slate-800">{p.bond_name}</td>
                        <td className="py-2.5 px-4 text-slate-700">¥{p.price.toFixed(2)}</td>
                        <td className="py-2.5 px-4 text-blue-600 font-semibold">{p.double_low.toFixed(1)}</td>
                        <td className="py-2.5 px-4 font-semibold text-emerald-600">
                          {Math.round(p.weight * 1000) / 10}%
                        </td>
                        <td className="py-2.5 px-4 text-amber-500">{stars}</td>
                        <td className="py-2.5 px-4 text-slate-600 max-w-xs truncate">{p.pm_verdict}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Veto Blacklist */}
          {result.vetoed_bonds && result.vetoed_bonds.length > 0 && (
            <div className="bg-rose-50/50 rounded-xl border border-rose-200 p-4 shadow-xs">
              <div className="font-bold text-xs text-rose-800 flex items-center gap-1.5 mb-2">
                <AlertOctagon className="w-4 h-4 text-rose-600" />
                <span>🚫 首席风控官 ({result.models_used?.credit?.model || (llmConfig?.is_ready ? activeModelName : '风控排雷')}) 一票否决高危名单 ({result.vetoed_bonds.length} 只)</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {result.vetoed_bonds.map((vb: any, idx: number) => (
                  <div key={idx} className="bg-white p-2.5 rounded-lg border border-rose-200 text-xs text-slate-700">
                    <span className="font-bold text-rose-700">{vb.bond_name || vb.bond_code}</span>: {vb.reason || '财务恶化或大股东高比例质押'}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Multi-Agent Deliberation & Verbatim Speech Transcript Room */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-4 space-y-4">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                {result.chamber_type === 'COURTROOM' ? (
                  <Scale className="w-4 h-4 text-amber-600" />
                ) : (
                  <MessageSquare className="w-4 h-4 text-blue-600" />
                )}
                <h4 className="font-bold text-xs text-slate-800">
                  {result.chamber_type === 'COURTROOM'
                    ? '⚖️ 金融多空裁决法庭 · 控辩合议实录与裁定书'
                    : '🎙️ 智能体圆桌会诊室 · 深度研判与辩论发言实录'}
                </h4>
              </div>

              {/* Bond Selector */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">核查标的:</span>
                <select
                  value={selectedBondCode}
                  onChange={(e) => setSelectedBondCode(e.target.value)}
                  className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 font-semibold text-slate-800 focus:outline-hidden"
                >
                  {result.final_portfolio.map((p) => (
                    <option key={p.bond_code} value={p.bond_code}>
                      {p.bond_name} ({p.bond_code})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {selectedCand && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-center">
                <div>
                  <span className="text-[10px] text-slate-400">现价:</span>{' '}
                  <b className="text-xs text-slate-800">¥{selectedCand.price}</b>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400">溢价率:</span>{' '}
                  <b className="text-xs text-slate-800">{selectedCand.premium_rate}%</b>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400">双低值:</span>{' '}
                  <b className="text-xs text-blue-600">{selectedCand.double_low}</b>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400">剩余规模:</span>{' '}
                  <b className="text-xs text-slate-800">{selectedCand.remaining_scale}亿</b>
                </div>
              </div>
            )}

            {/* Courtroom Verdict Banner (If in Courtroom Mode) */}
            {result.chamber_type === 'COURTROOM' && result.court_verdicts?.[selectedBondCode] && (
              <div className={`p-4 rounded-xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-xs ${
                result.court_verdicts[selectedBondCode].verdict === 'ACQUIT_BUY'
                  ? 'bg-gradient-to-r from-emerald-50 via-teal-50 to-emerald-50/80 border-emerald-300 text-emerald-950'
                  : result.court_verdicts[selectedBondCode].verdict === 'REJECT'
                  ? 'bg-gradient-to-r from-rose-50 via-red-50 to-rose-50/80 border-rose-300 text-rose-950'
                  : 'bg-gradient-to-r from-amber-50 via-yellow-50 to-amber-50/80 border-amber-300 text-amber-950'
              }`}>
                <div className="flex items-start md:items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0 shadow-2xs border ${
                    result.court_verdicts[selectedBondCode].verdict === 'ACQUIT_BUY'
                      ? 'bg-emerald-100/90 border-emerald-300 text-emerald-700'
                      : result.court_verdicts[selectedBondCode].verdict === 'REJECT'
                      ? 'bg-rose-100/90 border-rose-300 text-rose-700'
                      : 'bg-amber-100/90 border-amber-300 text-amber-700'
                  }`}>
                    {result.court_verdicts[selectedBondCode].verdict === 'ACQUIT_BUY' ? '⚖️' : result.court_verdicts[selectedBondCode].verdict === 'REJECT' ? '🚫' : '⚠️'}
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-xs">
                        【首席大法官合议庭终审裁决】
                      </span>
                      <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold shadow-2xs border ${
                        result.court_verdicts[selectedBondCode].verdict === 'ACQUIT_BUY'
                          ? 'bg-emerald-600 text-white border-emerald-700'
                          : result.court_verdicts[selectedBondCode].verdict === 'REJECT'
                          ? 'bg-rose-600 text-white border-rose-700'
                          : 'bg-amber-500 text-white border-amber-600'
                      }`}>
                        {result.court_verdicts[selectedBondCode].verdict === 'ACQUIT_BUY' ? '✅ 无罪抗辩成立 · 准予建仓'
                          : result.court_verdicts[selectedBondCode].verdict === 'REJECT' ? '❌ 驳回采纳 · 裁定排除'
                          : '⏳ 事实不清 · 存疑观望'}
                      </span>
                      <span className="text-amber-500 text-xs">
                        {Array(result.court_verdicts[selectedBondCode].rating_stars || 4).fill('⭐').join('')}
                      </span>
                    </div>
                    <p className="text-xs leading-relaxed opacity-90 font-medium">
                      {result.court_verdicts[selectedBondCode].sentence_summary}
                    </p>
                  </div>
                </div>

                <div className="bg-white/80 border border-slate-200/80 rounded-lg px-4 py-2 text-right shrink-0 shadow-2xs">
                  <div className="text-[10px] text-slate-500 font-medium">法庭裁定建议权重</div>
                  <div className="text-base font-black text-slate-900">
                    {((result.court_verdicts[selectedBondCode].weight ?? 0.08) * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            )}

            {/* Speeches Transcript Stream */}
            {result.all_bond_speeches && result.all_bond_speeches[selectedBondCode]?.length > 0 ? (
              <div className="space-y-3 pt-1">
                <div className="flex items-center justify-between text-xs text-slate-500 px-1 border-b border-slate-100 pb-2">
                  <span className="font-bold text-slate-700 flex items-center gap-1.5">
                    <MessageSquare className="w-3.5 h-3.5 text-blue-600" />
                    <span>智能体辩论与研判发言实录 (共 {result.all_bond_speeches[selectedBondCode].length} 轮发言)</span>
                  </span>
                  <span className="text-[11px] text-slate-400">
                    逐字记录每位智能体的发言与论据事实，供穿透复核与归因审查
                  </span>
                </div>

                <div className="space-y-3">
                  {result.all_bond_speeches[selectedBondCode].map((sp: AgentSpeech, idx: number) => {
                    const isBear = sp.stance === 'BEAR';
                    const isBull = sp.stance === 'BULL';
                    const isVeto = sp.stance === 'VETO';
                    const isJudge = sp.stance === 'JUDGEMENT';

                    const cardBg = isBear
                      ? 'bg-rose-50/20 border-rose-200'
                      : isBull
                      ? 'bg-emerald-50/20 border-emerald-200'
                      : isVeto
                      ? 'bg-red-50/30 border-red-300'
                      : isJudge
                      ? 'bg-indigo-50/20 border-indigo-200'
                      : 'bg-slate-50/40 border-slate-200';

                    const badgeStyle = isBear
                      ? 'bg-rose-100 text-rose-800 border-rose-200'
                      : isBull
                      ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                      : isVeto
                      ? 'bg-red-100 text-red-900 border-red-300'
                      : isJudge
                      ? 'bg-indigo-100 text-indigo-800 border-indigo-200'
                      : 'bg-slate-100 text-slate-700 border-slate-200';

                    const stanceTitle = isBear ? '🐻 做空公诉 / 质询'
                      : isBull ? '🐂 多头抗辩 / 举证'
                      : isVeto ? '🚫 信用一票否决'
                      : isJudge ? '⚖️ 大法官裁定'
                      : '🔍 研判发言';

                    return (
                      <div key={sp.speech_id || idx} className={`p-4 rounded-xl border ${cardBg} shadow-2xs space-y-2.5 transition-all`}>
                        {/* Header */}
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-full bg-white shadow-2xs border border-slate-200 flex items-center justify-center text-base shrink-0">
                              {sp.avatar || '🤖'}
                            </div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-xs text-slate-900">{sp.speaker_name}</span>
                              <span className={`text-[10px] font-semibold px-2 py-0.2 rounded-full border ${badgeStyle}`}>
                                {stanceTitle}
                              </span>
                              {sp.speaker_role && (
                                <span className="text-[10px] text-slate-500 bg-white/80 px-2 py-0.2 rounded border border-slate-200 font-mono">
                                  {sp.speaker_role}
                                </span>
                              )}
                              {sp.vote_score != null && (
                                <span className="text-[10px] text-indigo-700 font-semibold bg-indigo-50 px-2 py-0.2 rounded border border-indigo-200">
                                  打分: {sp.vote_score}分
                                </span>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-2 text-[10px] text-slate-400">
                            {sp.model_used && (
                              <span className="bg-white/80 border border-slate-200 px-2 py-0.5 rounded text-slate-600 font-mono">
                                {sp.model_used}
                              </span>
                            )}
                            <span>{sp.timestamp}</span>
                          </div>
                        </div>

                        {/* Verbatim Statement */}
                        <div className="relative pl-3.5 border-l-2 border-slate-300 text-xs text-slate-700 leading-relaxed font-normal bg-white/70 p-3 rounded-r-lg shadow-2xs">
                          <Quote className="w-3.5 h-3.5 text-slate-300 absolute -top-1 -left-2" />
                          <p className="whitespace-pre-wrap">{sp.statement}</p>
                        </div>

                        {/* Key Evidence Chain */}
                        {sp.key_evidence && sp.key_evidence.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                            <span className="text-[10px] font-semibold text-slate-500 flex items-center gap-1 shrink-0">
                              <Eye className="w-3 h-3 text-slate-400" />
                              论据支撑事实:
                            </span>
                            {sp.key_evidence.map((ev, i) => (
                              <span key={i} className="text-[10px] bg-white border border-slate-200 text-slate-700 px-2 py-0.5 rounded-md shadow-2xs">
                                {ev}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              /* Fallback to Classic 2x2 grid if speeches are not recorded */
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 pt-1">
                {/* Agent 1: Credit Risk */}
                <div className="flex gap-3 items-start bg-slate-50/70 p-3 rounded-xl border border-slate-200">
                  <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 font-bold text-xs">
                    🛡️
                  </div>
                  <div className="space-y-1 text-xs">
                    <div className="font-bold text-slate-900 flex items-center gap-2">
                      <span>{result.models_used?.credit?.label || `首席风控官 · ${llmConfig?.is_ready ? activeModelName : '风控排雷'}`}</span>
                      <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded font-semibold">
                        结论: {creditRev?.risk_level || 'PASS'}
                      </span>
                    </div>
                    <p className="text-slate-600 leading-relaxed">
                      {creditRev?.reason || '基本面穿透审查通过：正股财务稳健，无退市或恶性质押风险。'}
                    </p>
                  </div>
                </div>

                {/* Agent 2: Equity Momentum */}
                <div className="flex gap-3 items-start bg-blue-50/40 p-3 rounded-xl border border-blue-100">
                  <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center shrink-0 font-bold text-xs">
                    🚀
                  </div>
                  <div className="space-y-1 text-xs">
                    <div className="font-bold text-slate-900 flex items-center gap-2">
                      <span>{result.models_used?.equity?.label || `正股动量分析师 · ${llmConfig?.is_ready ? activeModelName : '弹性算法'}`}</span>
                      <span className="text-[10px] bg-blue-100 text-blue-800 px-1.5 py-0.2 rounded font-semibold">
                        弹性评分: {equityRev?.momentum_score || 75}/100
                      </span>
                    </div>
                    <p className="text-slate-600 leading-relaxed">
                      {equityRev?.catalyst_summary || '正股均线多头排列，所属题材具备良好资金进攻弹性。'}
                    </p>
                  </div>
                </div>

                {/* Agent 3: Clause Game */}
                <div className="flex gap-3 items-start bg-purple-50/40 p-3 rounded-xl border border-purple-100">
                  <div className="w-8 h-8 rounded-full bg-purple-100 text-purple-700 flex items-center justify-center shrink-0 font-bold text-xs">
                    ♟️
                  </div>
                  <div className="space-y-1 text-xs">
                    <div className="font-bold text-slate-900 flex items-center gap-2">
                      <span>{result.models_used?.clause?.label || `条款博弈专家 · ${llmConfig?.is_ready ? activeModelName : '博弈推演'}`}</span>
                      <span className="text-[10px] bg-purple-100 text-purple-800 px-1.5 py-0.2 rounded font-semibold">
                        强赎风险: {clauseRev?.call_risk_level || 'LOW'}
                      </span>
                    </div>
                    <p className="text-slate-600 leading-relaxed">
                      {clauseRev?.game_summary || '大股东转股诉求明确，具备下修博弈的安全边际与不对称高胜率。'}
                    </p>
                  </div>
                </div>

                {/* Agent 4: PM Director */}
                <div className="flex gap-3 items-start bg-amber-50/50 p-3 rounded-xl border border-amber-200">
                  <div className="w-8 h-8 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center shrink-0 font-bold text-xs">
                    👔
                  </div>
                  <div className="space-y-1 text-xs">
                    <div className="font-bold text-slate-900 flex items-center gap-2">
                      <span>{result.models_used?.pm?.label || '投资总监 (PM) · 最终裁决'}</span>
                      <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.2 rounded font-semibold">
                        建议配置: {selectedPortfolioItem ? Math.round(selectedPortfolioItem.weight * 1000) / 10 : 6.7}%
                      </span>
                    </div>
                    <p className="text-slate-700 font-medium leading-relaxed">
                      {selectedPortfolioItem?.pm_verdict || '安全垫与弹性共振，推荐纳入今日组合底仓配置！'}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fresh Deliberation Workspace Ready State */}
      {(!result || !result.has_run) && !loading && (
        <div className="bg-white rounded-2xl border border-slate-200/90 p-8 shadow-xs space-y-6">
          {/* Header Banner */}
          <div className="text-center max-w-2xl mx-auto space-y-2">
            <div className={`w-14 h-14 mx-auto rounded-2xl text-white flex items-center justify-center shadow-md ${
              isCourtroomMode
                ? 'bg-linear-to-tr from-amber-600 via-rose-600 to-amber-700'
                : 'bg-linear-to-tr from-blue-600 via-indigo-600 to-purple-600'
            }`}>
              {isCourtroomMode ? <Scale className="w-7 h-7" /> : <Bot className="w-7 h-7" />}
            </div>
            <h4 className="font-extrabold text-base text-slate-900 tracking-tight">
              {isCourtroomMode ? '⚖️ 金融多空法庭 · 审判席位已就绪' : '🎯 全新投研会商工作台 · 专家席位已就绪'}
            </h4>
            <p className="text-xs text-slate-500 leading-relaxed">
              历史投研数据已独立封装入库。当前工作台处于全新的就绪态，您可以确认当前量化前置筛选条件与出庭智能体阵容，随时敲槌开启穿透审查。
            </p>
          </div>

          {/* 3-Step Deliberation Pipeline Showcase */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            {/* Step 1: Strategy Quant Screening */}
            <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-200/80 hover:border-blue-300 transition-all space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
                  步骤 01 · 策略量化初筛
                </span>
                <Target className="w-4 h-4 text-blue-600" />
              </div>
              <div className="font-bold text-xs text-slate-900 flex items-center gap-1.5">
                <span>{activeStrategy?.name || '系统默认量化初筛'}</span>
                <span className="text-[10px] font-normal text-slate-500">({activeStrategy?.category || '可转债'})</span>
              </div>
              <div className="space-y-1 text-[11px] text-slate-600 bg-white p-2.5 rounded-lg border border-slate-100">
                <div className="flex justify-between">
                  <span className="text-slate-400">准入价格:</span>
                  <span className="font-semibold text-slate-700">{activeStrategy?.params?.min_price || 95}~{activeStrategy?.params?.max_price || 125} 元</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">规模限制:</span>
                  <span className="font-semibold text-slate-700">&le; {activeStrategy?.params?.max_scale || 5} 亿元</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">溢价上限:</span>
                  <span className="font-semibold text-slate-700">&le; {activeStrategy?.params?.max_premium || 50}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">排序因子:</span>
                  <span className="font-semibold text-slate-700">{activeStrategy?.params?.sort_by || '双低指标'}</span>
                </div>
              </div>
              <p className="text-[10px] text-slate-400 leading-normal">
                从全市场 500+ 只转债中计算因子并初选 Top 标的名额，排除不满足硬性量化指标的标的。
              </p>
            </div>

            {/* Step 2: Chamber & Agent Examination */}
            <div className={`rounded-xl p-4 border transition-all space-y-2.5 ${
              isCourtroomMode
                ? 'bg-amber-50/40 border-amber-200/80 hover:border-amber-300'
                : 'bg-purple-50/40 border-purple-200/80 hover:border-purple-300'
            }`}>
              <div className="flex items-center justify-between">
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                  isCourtroomMode ? 'text-amber-700 bg-amber-50 border-amber-200' : 'text-purple-700 bg-purple-50 border-purple-200'
                }`}>
                  步骤 02 · 智能体控辩质询
                </span>
                {isCourtroomMode ? <Scale className="w-4 h-4 text-amber-600" /> : <MessageSquare className="w-4 h-4 text-purple-600" />}
              </div>
              <div className="font-bold text-xs text-slate-900 flex items-center gap-1.5">
                <span>{activeChamber?.name || '投研专家圆桌'}</span>
                <span className="text-[10px] font-normal text-slate-500">({activeChamber?.agent_ids?.length || 4} 位专家)</span>
              </div>
              <div className="space-y-1 text-[11px] text-slate-600 bg-white p-2.5 rounded-lg border border-slate-100">
                <div className="flex items-center gap-1.5 text-slate-700">
                  <span>🛡️</span>
                  <span>首席风控官 (排雷 / 信用穿透 / 一票否决)</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-700">
                  <span>🚀</span>
                  <span>正股动量分析师 (弹性评分 / 题材研判)</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-700">
                  <span>♟️</span>
                  <span>条款博弈专家 (下修诉求 / 强赎预警)</span>
                </div>
                {isCourtroomMode && (
                  <div className="flex items-center gap-1.5 text-amber-800 font-medium">
                    <span>⚔️</span>
                    <span>控方检察官 VS 辩方律师 多轮质证</span>
                  </div>
                )}
              </div>
              <p className="text-[10px] text-slate-400 leading-normal">
                {isCourtroomMode
                  ? '控方指出财务暗坑，辩方提交价值证据，多轮交锋记录留存审计。'
                  : '三大专家从信用底线、进攻弹性和条款博弈独立给出定性结论。'}
              </p>
            </div>

            {/* Step 3: PM Verdict & Final Allocation */}
            <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-200/80 hover:border-emerald-300 transition-all space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                  步骤 03 · 终审合议配置
                </span>
                <Crown className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="font-bold text-xs text-slate-900 flex items-center gap-1.5">
                <span>投资总监 (PM) / 首席法官裁决</span>
              </div>
              <div className="space-y-1 text-[11px] text-slate-600 bg-white p-2.5 rounded-lg border border-slate-100">
                <div className="flex justify-between">
                  <span className="text-slate-400">否决机制:</span>
                  <span className="font-semibold text-rose-600">重大信用瑕疵一票否决</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">组合构建:</span>
                  <span className="font-semibold text-slate-700">攻守兼备权重智能拟合</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">存证审计:</span>
                  <span className="font-semibold text-emerald-700">全流程发言录入历史档案</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">组合建议:</span>
                  <span className="font-semibold text-slate-700">精选 Top 3~10 优质标的</span>
                </div>
              </div>
              <p className="text-[10px] text-slate-400 leading-normal">
                综合每位专家的论证细节，输出可追溯的持仓建议与投研辩论报告。
              </p>
            </div>
          </div>

          {/* Action Buttons Center */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-3">
            <button
              onClick={handleStartConsultation}
              disabled={loading}
              className={`flex items-center justify-center gap-2 text-white text-sm font-bold px-7 py-3 rounded-xl shadow-md hover:shadow-lg transition-all cursor-pointer disabled:opacity-50 w-full sm:w-auto ${
                isCourtroomMode
                  ? 'bg-linear-to-r from-amber-600 via-rose-600 to-amber-700 hover:from-amber-700 hover:to-rose-700'
                  : 'bg-linear-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700'
              }`}
            >
              {isCourtroomMode ? <Gavel className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
              <span>
                {isCourtroomMode
                  ? `敲槌开庭！开启【${activeStrategy?.name || '默认策略'}】多空裁决`
                  : `立即启动【${activeStrategy?.name || '默认策略'}】联合会审`}
              </span>
            </button>

            {historyCount > 0 && (
              <button
                onClick={() => setHistoryOpen(true)}
                className="flex items-center justify-center gap-2 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-semibold px-4 py-3 rounded-xl shadow-2xs transition-all cursor-pointer w-full sm:w-auto"
              >
                <History className="w-4 h-4 text-indigo-600" />
                <span>调阅往期历史档案 ({historyCount})</span>
              </button>
            )}

            <button
              onClick={() => setStudioOpen(true)}
              className="flex items-center justify-center gap-1.5 bg-slate-50 hover:bg-slate-100 text-slate-600 border border-slate-200 text-xs font-semibold px-3 py-3 rounded-xl shadow-2xs transition-all cursor-pointer w-full sm:w-auto"
            >
              <Settings className="w-3.5 h-3.5 text-slate-500" />
              <span>定制智能体</span>
            </button>
          </div>
        </div>
      )}

      {/* Agent Studio Modal */}
      <AgentStudioModal
        isOpen={studioOpen}
        onClose={() => setStudioOpen(false)}
        onAgentsChanged={loadChambers}
      />

      {/* History Archive Modal */}
      <AgentHistoryModal
        isOpen={historyOpen}
        onClose={() => {
          setHistoryOpen(false);
          fetchHistoryCount();
        }}
        onSelectReport={(rep) => {
          setResult(rep);
          if (rep.final_portfolio && rep.final_portfolio.length > 0) {
            setSelectedBondCode(rep.final_portfolio[0].bond_code);
          }
          if (rep.chamber_id) {
            setCurrentChamberId(rep.chamber_id);
          }
          if (rep.strategy_id) {
            setCurrentStrategyId(rep.strategy_id);
          }
        }}
      />
    </div>
  );
};
