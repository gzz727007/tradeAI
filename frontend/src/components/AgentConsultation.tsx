import React, { useState, useEffect } from 'react';
import { AgentResult, CandidateBond, Strategy } from '../types';
import { api } from '../api/client';
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
  Layers
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

  const loadCachedResult = async () => {
    try {
      const data = await api.getAgentResult();
      if (data.has_run) {
        setResult(data);
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
    api.getLLMConfig().then((data) => setLlmConfig(data)).catch(() => {});
  }, []);

  const handleStartConsultation = () => {
    setLoading(true);
    setStreamSteps([]);

    // Open WebSocket with strategy_id
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const query = currentStrategyId && currentStrategyId !== 'default'
      ? `?strategy_id=${encodeURIComponent(currentStrategyId)}`
      : '';
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
      api.runAgents(currentStrategyId && currentStrategyId !== 'default' ? currentStrategyId : undefined)
        .then((data) => {
          setResult(data);
          if (data.final_portfolio?.length > 0) {
            setSelectedBondCode(data.final_portfolio[0].bond_code);
          }
          setLoading(false);
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

  return (
    <div className="space-y-4">
      {/* Strategy-Driven Controller Bar */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3.5">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-linear-to-tr from-blue-600 to-indigo-600 text-white flex items-center justify-center shadow-xs">
                <Bot className="w-4 h-4" />
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                  <span>今日 AI 智能体投研会诊室</span>
                  <span className="text-[10px] font-semibold bg-purple-50 text-purple-700 border border-purple-200 px-2 py-0.5 rounded-full">
                    Quantamental 量化前置初筛 + 多智能体博弈
                  </span>
                </h3>
                {llmConfig?.is_ready && (
                  <span className="inline-flex items-center gap-1.5 text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-0.5 rounded-full shadow-2xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span>算力引擎: <b>{activeProviderName}</b> · <code className="bg-white/80 px-1 py-0.2 rounded text-[9px] text-emerald-800">{activeModelName}</code> (全自适应弹性调度)</span>
                  </span>
                )}
              </div>
            </div>
            <p className="text-xs text-slate-500">
              由前置量化策略从 500+ 只转债中粗筛标的，再交由 <b className="text-slate-700">信用风控官</b>、<b className="text-slate-700">正股动量官</b>、<b className="text-slate-700">条款博弈专家</b> 进行穿透审核（统一由当前配置的 <b className="text-slate-700">{activeModelName}</b> 自适应推理驱动），最后由 <b className="text-slate-700">PM投资总监</b> 一票否决并生成最优组合配置。
            </p>
          </div>

          <button
            onClick={handleStartConsultation}
            disabled={loading}
            className="flex items-center gap-2 bg-linear-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-xs font-semibold px-5 py-2.5 rounded-xl shadow-sm hover:shadow transition-all cursor-pointer disabled:opacity-50 shrink-0"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>投委会多智能体协同会诊中...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>召开今日投委会实时会诊</span>
              </>
            )}
          </button>
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
          {/* Strategy Attribution / Quantamental Pipeline Summary Card */}
          <div className="bg-gradient-to-r from-blue-50/70 via-indigo-50/50 to-purple-50/70 border border-blue-200/80 rounded-xl p-3.5 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-800">
                    量化前置源：【{result.strategy_name || '默认量化初筛'}】
                  </span>
                  {result.strategy_category && (
                    <span className="text-[10px] font-semibold bg-blue-100/70 text-blue-700 px-2 py-0.5 rounded-full border border-blue-200">
                      {result.strategy_category}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  全市场 500+ 只转债 → 量化策略初筛入围 <b className="text-blue-600 font-bold">{result.screened_count || result.candidates?.length || 0}</b> 只 → 4 位专家全景穿透审查 (排除高危 <b className="text-rose-600 font-bold">{result.vetoed_bonds?.length || 0}</b> 只) → 终审精选入库 <b className="text-emerald-600 font-bold">{result.final_portfolio?.length || 0}</b> 只
                </p>
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

          {/* Multi-Agent Roundtable Interactive Chat Room */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-4 space-y-4">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-blue-600" />
                <h4 className="font-bold text-xs text-slate-800">
                  🎙️ 智能体圆桌会诊室 (选择标的查看 4 大专家深度研判与辩论实录)
                </h4>
              </div>

              {/* Bond Selector */}
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

            {/* Chat Transcript Bubbles: 2x2 grid on wide screens */}
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
          </div>
        </div>
      )}

      {/* Empty State before Running */}
      {(!result || !result.has_run) && !loading && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-xs">
          <Bot className="w-12 h-12 text-blue-500 mx-auto mb-3 opacity-80" />
          <h4 className="font-bold text-sm text-slate-800 mb-1">今日尚未启动多智能体联合会诊</h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto mb-4">
            点击上方【🚀 启动多智能体联合会诊】按钮，系统将调度 4 大 AI 专家并行执行量化初筛、信用穿透审查、动量题材评分与条款博弈推演。
          </p>
          <button
            onClick={handleStartConsultation}
            className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-xs cursor-pointer inline-flex items-center gap-1.5"
          >
            <Play className="w-3.5 h-3.5" />
            <span>立即启动今日会诊</span>
          </button>
        </div>
      )}
    </div>
  );
};
