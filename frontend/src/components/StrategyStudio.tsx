import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { Strategy, BacktestResult } from '../types';
import { api } from '../api/client';
import {
  Plus,
  Sparkles,
  Search,
  Trash2,
  Lock,
  FileText,
  Play,
  Trophy,
  Shield,
  Target,
  BarChart3,
  X,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Copy,
  Edit3,
  Save,
  RefreshCw,
  Layers,
  Bot
} from 'lucide-react';

interface StrategyStudioProps {
  startDate: string;
  endDate: string;
  rebalanceFreq: number;
  refreshKey?: number;
  onSendToAgent?: (strategyId: string) => void;
}

export const StrategyStudio: React.FC<StrategyStudioProps> = ({
  startDate,
  endDate,
  rebalanceFreq,
  refreshKey,
  onSendToAgent,
}) => {
  const [subView, setSubView] = useState<'library' | 'arena'>('library');
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingStrategies, setLoadingStrategies] = useState(false);
  const [selectedStrategyIds, setSelectedStrategyIds] = useState<string[]>([]);
  
  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [viewingStrategy, setViewingStrategy] = useState<Strategy | null>(null);

  // Form states
  const [newStratName, setNewStratName] = useState('');
  const [newStratDesc, setNewStratDesc] = useState('');
  const [newStratMinP, setNewStratMinP] = useState(95);
  const [newStratMaxP, setNewStratMaxP] = useState(125);
  const [newStratMaxScale, setNewStratMaxScale] = useState(5.0);
  const [newStratMaxPrem, setNewStratMaxPrem] = useState(50.0);
  const [newStratWeightDL, setNewStratWeightDL] = useState(1.0);
  const [newStratTopN, setNewStratTopN] = useState(15);
  const [newStratSortBy, setNewStratSortBy] = useState('double_low');

  // 三步向导: 意图 → 参数(手动/AI生成) → 回测验证
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [wizardMode, setWizardMode] = useState<'manual' | 'ai'>('manual');
  const [wizardError, setWizardError] = useState('');
  const [wizardCreatedId, setWizardCreatedId] = useState(''); // 第3步产生的临时策略 (放弃即删除)
  const [wizardBusy, setWizardBusy] = useState(false);
  const [wizardPreview, setWizardPreview] = useState<BacktestResult | null>(null);

  // AI discovery form
  const [aiIdea, setAiIdea] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiMode, setAiMode] = useState<'discover' | 'evolve'>('discover');
  const [viewingCodeStrategy, setViewingCodeStrategy] = useState<Strategy | null>(null);
  const [showExperiments, setShowExperiments] = useState(false);
  const [experiments, setExperiments] = useState<any[]>([]);
  const [loadingExperiments, setLoadingExperiments] = useState(false);

  const loadExperiments = async () => {
    setLoadingExperiments(true);
    try {
      setExperiments(await api.listExperiments(100));
    } finally {
      setLoadingExperiments(false);
    }
  };

  // 查找某策略对应的评审意见 (成功实验的 _review 明细)
  const findReviewFor = (strategyId: string) => {
    const exp = experiments.find((e) => e.strategy_id === strategyId && e.status === 'succeeded');
    return exp?.metrics?._review || [];
  };
  const [llmStatus, setLlmStatus] = useState<any>(null);


  // Backtest
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [backtestError, setBacktestError] = useState('');
  const [backtestMode, setBacktestMode] = useState<'real' | 'fast'>('real');

  // Editing & Cloning state inside unified modal
  const [isEditingInModal, setIsEditingInModal] = useState<boolean>(false);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editMinP, setEditMinP] = useState(95);
  const [editMaxP, setEditMaxP] = useState(125);
  const [editMaxScale, setEditMaxScale] = useState(5.0);
  const [editMaxPrem, setEditMaxPrem] = useState(50.0);
  const [editWeightDL, setEditWeightDL] = useState(1.0);
  const [editTopN, setEditTopN] = useState(15);
  const [editSortBy, setEditSortBy] = useState('double_low');
  const [isEditCloneMode, setIsEditCloneMode] = useState(false);

  const loadStrategies = async (retries = 3) => {
    try {
      setLoadingStrategies(true);
      const data = await api.getStrategies();
      if ((!data || data.length === 0) && retries > 0) {
        // 如果后端服务正在启动或连接中，自动间隔重试
        setTimeout(() => loadStrategies(retries - 1), 1000);
        return;
      }
      setStrategies(data || []);
      if (selectedStrategyIds.length === 0 && data && data.length > 0) {
        setSelectedStrategyIds(data.slice(0, 3).map((s) => s.id));
      }
    } catch (err) {
      console.error('Failed to load strategies', err);
      if (retries > 0) {
        setTimeout(() => loadStrategies(retries - 1), 1200);
      }
    } finally {
      setLoadingStrategies(false);
    }
  };

  useEffect(() => {
    loadStrategies();
  }, [refreshKey]);

  useEffect(() => {
    if (isAiModalOpen) {
      api.getLLMConfig().then((data) => setLlmStatus(data)).catch(() => {});
    }
  }, [isAiModalOpen]);


  // ===== 三步向导逻辑: 意图 → 参数 → 回测验证 =====
  const buildWizardParams = () => ({
    min_price: Number(newStratMinP),
    max_price: Number(newStratMaxP),
    max_scale: Number(newStratMaxScale),
    max_premium: Number(newStratMaxPrem),
    double_low_weight: Number(newStratWeightDL),
    top_n: Number(newStratTopN),
    sort_by: newStratSortBy,
    // YTM 是"越高越稳健", 与双低/价格/溢价率的"越低越优"方向相反
    sort_ascending: newStratSortBy !== 'ytm',
  });

  const validateWizardParams = (): string => {
    if (!newStratName.trim()) return '请填写策略名称';
    if (Number(newStratMinP) >= Number(newStratMaxP)) return '价格下限必须小于价格上限';
    if (Number(newStratTopN) < 1 || Number(newStratTopN) > 50) return '持仓数量需在 1~50 之间';
    if (Number(newStratMaxPrem) < 0) return '转股溢价率上限不能为负';
    if (Number(newStratMaxScale) <= 0) return '规模上限必须为正';
    return '';
  };

  // AI 按意图生成参数建议 (ai-discover 会自动入库, 返回的 strategy.id 作为临时策略, 放弃即删)
  const handleWizardAiGen = async () => {
    if (!newStratDesc.trim()) { setWizardError('请先在第 1 步填写策略逻辑描述, AI 依据它生成参数'); return; }
    setWizardBusy(true); setWizardError('');
    try {
      const res = await api.aiDiscoverStrategy(newStratDesc);
      const p = res.strategy?.params || {};
      if (p.min_price != null) setNewStratMinP(p.min_price);
      if (p.max_price != null) setNewStratMaxP(p.max_price);
      if (p.max_scale != null) setNewStratMaxScale(p.max_scale);
      if (p.max_premium != null) setNewStratMaxPrem(p.max_premium);
      if (p.double_low_weight != null) setNewStratWeightDL(p.double_low_weight);
      if (p.top_n != null) setNewStratTopN(p.top_n);
      if (p.sort_by) setNewStratSortBy(p.sort_by);
      if (res.strategy?.id) setWizardCreatedId(res.strategy.id);
      if (res.strategy?.name && !newStratName.trim()) setNewStratName(res.strategy.name);
      setWizardMode('ai');
      setWizardError('');
    } catch (err) {
      setWizardError(err instanceof Error ? err.message : 'AI 生成参数失败');
    } finally {
      setWizardBusy(false);
    }
  };

  // 第 2 步 → 第 3 步: 落库 (AI模式更新微调参数 / 手动模式创建) + 立即回测近两年
  const runWizardPreview = async () => {
    const v = validateWizardParams();
    if (v) { setWizardError(v); return; }
    setWizardBusy(true); setWizardError('');
    try {
      let sid = wizardCreatedId;
      if (sid && wizardMode === 'ai') {
        await api.updateStrategy(sid, { name: newStratName.trim(), description: newStratDesc.trim(), params: buildWizardParams() });
      } else {
        const res = await api.createStrategy({
          name: newStratName.trim(),
          description: newStratDesc.trim() || '用户自定义策略',
          category: '用户自定义',
          params: buildWizardParams(),
        });
        sid = res.strategy.id;
        setWizardCreatedId(sid);
      }
      const fmt = (d: Date) => d.toISOString().slice(0, 10).replace(/-/g, '');
      const bt = await api.runBacktest([sid], fmt(new Date(Date.now() - 730 * 86400000)), fmt(new Date()), 5, 'real');
      setWizardPreview(bt);
      setWizardStep(3);
    } catch (err) {
      setWizardError(err instanceof Error ? err.message : '回测预览失败');
    } finally {
      setWizardBusy(false);
    }
  };

  // 放弃: 删除临时策略并关闭 (第1/2步时 createdId 为空, 纯关闭)
  const abandonWizard = async () => {
    if (wizardCreatedId) {
      try { await api.deleteStrategy(wizardCreatedId); } catch { /* 删除失败不阻塞关闭 */ }
    }
    setIsCreateModalOpen(false);
  };

  // 确认入库: 刷新列表并选中
  const confirmWizard = async () => {
    await loadStrategies();
    if (wizardCreatedId) {
      setSelectedStrategyIds((prev) => [...prev.filter((id) => id !== wizardCreatedId), wizardCreatedId]);
    }
    setIsCreateModalOpen(false);
  };

  const handleAiDiscover = async () => {
    setAiGenerating(true);
    try {
      await api.aiDiscoverStrategy(aiIdea);
      setAiGenerating(false);
      setIsAiModalOpen(false);
      setAiIdea('');
      loadStrategies();
    } catch (err) {
      setAiGenerating(false);
      // 如实展示后端返回的真实失败原因 (如 LLM 连续失败/未配置)
      alert(err instanceof Error ? err.message : 'AI探索策略失败');
    }
  };

  const handleAiEvolve = async () => {
    setAiGenerating(true);
    try {
      const res = await api.aiEvolveStrategy(aiIdea, 3);
      setAiGenerating(false);
      setIsAiModalOpen(false);
      setAiIdea('');
      loadStrategies();
      const rounds = res.rounds || [];
      const succeedRound = rounds.find((r: any) => r.status === 'succeeded');
      const metricSummary = succeedRound?.metrics?.total_return != null
        ? `，全量回测累计收益 ${(succeedRound.metrics.total_return * 100).toFixed(1)}%`
        : '';
      const usedRounds = succeedRound?.round || rounds.length;
      alert(`AI 代码进化成功 (${usedRounds} 轮迭代通过验证${metricSummary})。\n\n策略「${res.strategy?.name || ''}」已入库。接下来:\n1. 在策略卡片点「查看代码」审阅 AI 写的代码与评审团意见\n2. 点「对决」跑历史回测验证\n3. 到「模拟锦标赛」将策略投入实时模拟盘`);
    } catch (err) {
      setAiGenerating(false);
      alert(err instanceof Error ? err.message : 'AI 策略进化失败');
    }
  };

  const openStrategyModal = (strat: Strategy, startEditing: boolean = false, isClone: boolean = false) => {
    setViewingStrategy(strat);
    setIsEditingInModal(startEditing);
    setIsEditCloneMode(isClone);
    setEditName(isClone ? `${strat.name} (副本)` : strat.name);
    setEditDesc(isClone ? `基于【${strat.name}】微调参数创建。${strat.description}` : strat.description);
    const p = strat.params || {};
    setEditMinP(p.min_price ?? 95);
    setEditMaxP(p.max_price ?? 125);
    setEditMaxScale(p.max_scale ?? 5.0);
    setEditMaxPrem(p.max_premium ?? 50.0);
    setEditWeightDL(p.double_low_weight ?? 1.0);
    setEditTopN(p.top_n ?? 15);
    setEditSortBy(p.sort_by ?? 'double_low');
  };

  const startEditingCurrent = (isClone: boolean = false) => {
    if (!viewingStrategy) return;
    setIsEditingInModal(true);
    setIsEditCloneMode(isClone);
    setEditName(isClone ? `${viewingStrategy.name} (副本)` : viewingStrategy.name);
    setEditDesc(isClone ? `基于【${viewingStrategy.name}】微调参数创建。${viewingStrategy.description}` : viewingStrategy.description);
    const p = viewingStrategy.params || {};
    setEditMinP(p.min_price ?? 95);
    setEditMaxP(p.max_price ?? 125);
    setEditMaxScale(p.max_scale ?? 5.0);
    setEditMaxPrem(p.max_premium ?? 50.0);
    setEditWeightDL(p.double_low_weight ?? 1.0);
    setEditTopN(p.top_n ?? 15);
    setEditSortBy(p.sort_by ?? 'double_low');
  };

  const handleSaveEdit = async (e?: React.FormEvent, runBattleAfter: boolean = false) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!viewingStrategy || !editName.trim()) return;

    try {
      if (isEditCloneMode || viewingStrategy.category === '系统内置') {
        const res = await api.createStrategy({
          name: editName.trim(),
          description: editDesc.trim(),
          category: '用户自定义',
          params: {
            min_price: Number(editMinP),
            max_price: Number(editMaxP),
            max_scale: Number(editMaxScale),
            max_premium: Number(editMaxPrem),
            double_low_weight: Number(editWeightDL),
            top_n: Number(editTopN),
            sort_by: editSortBy,
            sort_ascending: editSortBy !== 'ytm',
          },
        });
        await loadStrategies();
        setIsEditingInModal(false);

        if (res.strategy && res.strategy.id) {
          setSelectedStrategyIds((prev) => [
            ...prev.filter((id) => id !== res.strategy.id),
            res.strategy.id,
          ]);
          setViewingStrategy(res.strategy);
        }

        if (runBattleAfter) {
          setViewingStrategy(null);
          setSubView('arena');
        }
      } else {
        await api.updateStrategy(viewingStrategy.id, {
          name: editName.trim(),
          description: editDesc.trim(),
          params: {
            min_price: Number(editMinP),
            max_price: Number(editMaxP),
            max_scale: Number(editMaxScale),
            max_premium: Number(editMaxPrem),
            double_low_weight: Number(editWeightDL),
            top_n: Number(editTopN),
            sort_by: editSortBy,
            sort_ascending: editSortBy !== 'ytm',
          },
        });
        await loadStrategies();
        setViewingStrategy({
          ...viewingStrategy,
          name: editName.trim(),
          description: editDesc.trim(),
          params: {
            ...viewingStrategy.params,
            min_price: Number(editMinP),
            max_price: Number(editMaxP),
            max_scale: Number(editMaxScale),
            max_premium: Number(editMaxPrem),
            double_low_weight: Number(editWeightDL),
            top_n: Number(editTopN),
            sort_by: editSortBy,
            sort_ascending: editSortBy !== 'ytm',
          }
        });
        setIsEditingInModal(false);

        if (runBattleAfter) {
          setSelectedStrategyIds((prev) => Array.from(new Set([...prev, viewingStrategy.id])));
          setViewingStrategy(null);
          setSubView('arena');
        }
      }
    } catch (err: any) {
      alert(err.message || '保存策略失败');
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确定删除策略【${name}】吗？`)) return;
    try {
      await api.deleteStrategy(id);
      loadStrategies();
    } catch (err: any) {
      alert(err.message || '删除失败');
    }
  };

  const handleRunBacktest = async () => {
    if (selectedStrategyIds.length === 0) return;
    setBacktestRunning(true);
    setBacktestError('');
    try {
      const res = await api.runBacktest(selectedStrategyIds, startDate, endDate, rebalanceFreq, backtestMode);
      setBacktestResult(res);
      setBacktestRunning(false);
    } catch (err: any) {
      setBacktestError(err.message || '回测失败');
      setBacktestRunning(false);
    }
  };

  // ECharts Options
  const getNavChartOption = () => {
    if (!backtestResult) return {};
    const series = Object.entries(backtestResult.nav_series).map(([name, data]) => {
      const isBenchmark = name.includes('基准');
      return {
        name,
        type: 'line',
        data,
        smooth: true,
        showSymbol: false,
        lineStyle: {
          width: isBenchmark ? 1.5 : 2.5,
          type: isBenchmark ? 'dashed' : 'solid',
        },
      };
    });

    return {
      title: {
        text: '累计净值走势曲线 (Cumulative Equity Curves)',
        textStyle: { fontSize: 13, fontWeight: 'bold', color: '#1e293b' },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
      },
      legend: {
        bottom: 0,
        textStyle: { fontSize: 11, color: '#64748b' },
      },
      grid: {
        top: 40,
        left: 50,
        right: 20,
        bottom: 40,
      },
      xAxis: {
        type: 'category',
        data: backtestResult.dates,
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
      },
      series,
    };
  };

  const getDrawdownChartOption = () => {
    if (!backtestResult) return {};
    const series = Object.entries(backtestResult.drawdown_series).map(([name, data]) => ({
      name,
      type: 'line',
      data,
      smooth: true,
      showSymbol: false,
      areaStyle: { opacity: 0.15 },
      lineStyle: { width: 1.5 },
    }));

    return {
      title: {
        text: '水下动态回撤曲线 (Underwater Drawdown %)',
        textStyle: { fontSize: 13, fontWeight: 'bold', color: '#1e293b' },
      },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, textStyle: { fontSize: 10, color: '#64748b' } },
      grid: { top: 40, left: 50, right: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: backtestResult.dates,
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: '{value}%', color: '#94a3b8', fontSize: 10 },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
      },
      series,
    };
  };

  return (
    <div className="space-y-4">
      {/* Sub-view Segmented Switcher */}
      <div className="flex justify-center">
        <div className="bg-slate-200/80 p-1 rounded-xl inline-flex gap-1 shadow-inner">
          <button
            onClick={() => setSubView('library')}
            className={`px-5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              subView === 'library'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            📚 策略档案库 (Strategy Library)
          </button>
          <button
            onClick={() => {
              setSubView('arena');
              if (!backtestResult && !backtestRunning) {
                handleRunBacktest();
              }
            }}
            className={`px-5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              subView === 'arena'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            🏁 策略历史对决竞技场 (Backtest Arena)
          </button>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 视图 A: 策略库 (Library) */}
      {/* ======================================================== */}
      {subView === 'library' && (
        <div className="space-y-4">
          {/* Top Actions Row */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-slate-800">
                  当前量化策略档案库 (共 {strategies.length} 个独立策略)
                </span>
                {loadingStrategies && (
                  <span className="flex items-center gap-1 text-[11px] text-blue-600 font-medium bg-blue-50 px-2 py-0.5 rounded-md">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    正在同步...
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                每个策略拥有独立选券边界与交易纪律，在模拟盘与实盘中自负盈亏
              </p>
            </div>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button
                onClick={() => loadStrategies(0)}
                disabled={loadingStrategies}
                className="flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 text-xs font-semibold px-3 py-2 rounded-lg transition-colors cursor-pointer"
                title="刷新并重新读取策略库档案"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingStrategies ? 'animate-spin text-blue-600' : ''}`} />
                <span>刷新策略库</span>
              </button>
              <button
                onClick={() => {
                  setNewStratName(''); setNewStratDesc('');
                  setWizardStep(1); setWizardMode('manual'); setWizardError('');
                  setWizardCreatedId(''); setWizardPreview(null);
                  setIsCreateModalOpen(true);
                }}
                className="flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 text-xs font-semibold px-3 py-2 rounded-lg transition-colors cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>新建策略</span>
              </button>
              <button
                onClick={() => setIsAiModalOpen(true)}
                className="flex items-center gap-1.5 bg-linear-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-xs font-semibold px-3.5 py-2 rounded-lg shadow-xs transition-all cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>AI 探索新策略</span>
              </button>
              <button
                onClick={() => { setShowExperiments(true); if (!experiments.length) loadExperiments(); }}
                className="flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 border border-slate-200 text-xs font-semibold px-3 py-2 rounded-lg transition-colors cursor-pointer"
                title="查看 AI 代码进化的每轮实验: 代码/回测指标/评审意见"
              >
                <FileText className="w-3.5 h-3.5" />
                <span>实验记录</span>
              </button>
            </div>
          </div>

          {/* Cards Grid or Empty State */}
          {strategies.length === 0 ? (
            <div className="bg-white rounded-xl border border-dashed border-slate-300 p-12 text-center">
              <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-3">
                <Layers className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-800 mb-1">
                {loadingStrategies ? '正在连接策略档案库...' : '暂未读取到策略数据'}
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mb-4">
                {loadingStrategies
                  ? '系统正与本地量化引擎建立实时通信，请稍候...'
                  : '策略库可能正在加载，或服务正在启动。您可以点击下方按钮立即重试同步。'}
              </p>
              <button
                onClick={() => loadStrategies(0)}
                disabled={loadingStrategies}
                className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-xs transition-colors cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingStrategies ? 'animate-spin' : ''}`} />
                <span>立即重新读取策略档案</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-4">
            {strategies.map((s) => {
              const isBuiltin = s.category === '系统内置';
              const isAi = s.category?.includes('AI');
              const p = s.params || {};

              return (
                <div
                  key={s.id}
                  className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs hover:border-slate-300 hover:shadow-md transition-all flex flex-col justify-between"
                >
                  <div>
                    {/* Header */}
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <h3 className="font-bold text-slate-900 text-sm truncate flex items-center gap-1.5">
                        <span className="text-blue-600">📌</span> {s.name}
                      </h3>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${
                          isBuiltin
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : isAi
                            ? 'bg-purple-50 text-purple-700 border border-purple-200'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}
                      >
                        {s.category}
                      </span>
                    </div>

                    {/* Description */}
                    <p className="text-xs text-slate-500 line-clamp-2 h-8 leading-4 mb-3">
                      {s.description}
                    </p>

                    {/* 6-Cell Matrix / AI 代码策略专属信息 */}
                    {p.__code__ ? (
                      <div className="bg-indigo-50/60 p-2.5 rounded-lg border border-indigo-100 text-center mb-3">
                        <div className="grid grid-cols-3 gap-2 mb-1.5">
                          <div>
                            <div className="text-[10px] text-indigo-400 font-medium">策略类型</div>
                            <div className="text-xs font-bold text-indigo-800">
                              {(p.__code__.match(/BaseEventStrategy|BaseCBStrategy/) || [])[0] === 'BaseEventStrategy' ? '事件驱动' : '截面轮动'}
                            </div>
                          </div>
                          <div>
                            <div className="text-[10px] text-indigo-400 font-medium">代码规模</div>
                            <div className="text-xs font-bold text-indigo-800">{p.__code__.split('\n').length} 行</div>
                          </div>
                          <div>
                            <div className="text-[10px] text-indigo-400 font-medium">数据维度</div>
                            <div className="text-xs font-bold text-indigo-800">
                              {(p.__code__.match(/stock_market_cap|stock_mom_20|remaining_years|premium_rate|double_low/g) || []).length >= 2 ? '多维因子' : '单因子'}
                            </div>
                          </div>
                        </div>
                        <div className="text-[10px] text-indigo-500">AI 编写 · 沙箱验证 · 评审团审查通过</div>
                      </div>
                    ) : (
                    <div className="grid grid-cols-3 gap-2 bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-center mb-3">
                      <div>
                        <div className="text-[10px] text-slate-400 font-medium">价格区间</div>
                        <div className="text-xs font-bold text-slate-700">
                          {p.min_price || 90}~{p.max_price || 130}元
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 font-medium">溢价率上限</div>
                        <div className="text-xs font-bold text-slate-700">
                          &le; {p.max_premium || 70}%
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 font-medium">规模上限</div>
                        <div className="text-xs font-bold text-slate-700">
                          &le; {p.max_scale || 10}亿
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 font-medium">核心排序</div>
                        <div className="text-xs font-bold text-slate-700">
                          {p.sort_by || 'double_low'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 font-medium">双低权重 W</div>
                        <div className="text-xs font-bold text-slate-700">
                          {p.double_low_weight || 1.0}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 font-medium">目标持仓</div>
                        <div className="text-xs font-bold text-slate-700">
                          {p.top_n || 15} 只
                        </div>
                      </div>
                    </div>
                    )}
                  </div>

                  {/* Action Bar */}
                  <div className="flex items-center justify-between pt-2.5 border-t border-slate-100 gap-1.5">
                    {/* Primary Navigation & Action */}
                    <div className="flex items-center gap-1.5 flex-1 min-w-0">
                      {p.__code__ && (
                        <button
                          onClick={() => { setViewingCodeStrategy(s); if (!experiments.length) loadExperiments(); }}
                          className="flex items-center justify-center gap-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold py-1.5 px-2 rounded-lg border border-indigo-200 transition-colors cursor-pointer whitespace-nowrap truncate"
                          title="查看 AI 生成的策略代码与评审团意见"
                        >
                          <FileText className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                          <span>查看代码</span>
                        </button>
                      )}
                      <button
                        onClick={() => openStrategyModal(s, false, false)}
                        className="flex-1 flex items-center justify-center gap-1 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold py-1.5 px-2 rounded-lg border border-slate-200 transition-colors cursor-pointer whitespace-nowrap truncate"
                        title="查看完整逻辑与参数详情"
                      >
                        <FileText className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                        <span>查看档案</span>
                      </button>

                      <button
                        onClick={() => {
                          setSelectedStrategyIds((prev) => Array.from(new Set([...prev, s.id])));
                          setSubView('arena');
                        }}
                        className="flex items-center justify-center gap-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-xs font-semibold py-1.5 px-2.5 rounded-lg border border-emerald-200 transition-colors cursor-pointer whitespace-nowrap shrink-0"
                        title="将此策略加入对决阵容并切换到竞技场"
                      >
                        <Play className="w-3 h-3 fill-current" />
                        <span>对决</span>
                      </button>

                      {onSendToAgent && (
                        <button
                          onClick={() => onSendToAgent(s.id)}
                          className="flex items-center justify-center gap-1 bg-purple-50 hover:bg-purple-100 text-purple-700 text-xs font-semibold py-1.5 px-2.5 rounded-lg border border-purple-200 transition-colors cursor-pointer whitespace-nowrap shrink-0"
                          title="以此策略为标的池初筛源，移交今日AI智能体投委会进行多空会诊"
                        >
                          <Bot className="w-3 h-3 text-purple-600" />
                          <span>会诊</span>
                        </button>
                      )}
                    </div>

                    {/* Management Utilities */}
                    <div className="flex items-center gap-0.5 border-l border-slate-100 pl-1.5 shrink-0">
                      <button
                        onClick={() => openStrategyModal(s, true, true)}
                        className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors cursor-pointer"
                        title="复制并微调新策略 (Clone)"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>

                      {!isBuiltin ? (
                        <>
                          <button
                            onClick={() => openStrategyModal(s, true, false)}
                            className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors cursor-pointer"
                            title="修改本策略参数"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDelete(s.id, s.name)}
                            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                            title="删除策略"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      ) : (
                        <span
                          className="p-1.5 text-slate-300 cursor-not-allowed"
                          title="内置策略受系统保护"
                        >
                          <Lock className="w-3.5 h-3.5" />
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          )}
        </div>
      )}

      {/* ======================================================== */}
      {/* 视图 B: 历史对决竞技场 (Arena) */}
      {/* ======================================================== */}
      {subView === 'arena' && (
        <div className="space-y-4">
          {/* Strategy Selection & Control Bar */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs space-y-3">
            <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-3">
              <div>
                <h4 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                  <Trophy className="w-4 h-4 text-amber-500" />
                  <span>挑选参战策略阵容 (可多选对比)：</span>
                  <span className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full font-semibold">
                    已挂载本地数据湖 (1,038只/77.8万条)
                  </span>
                </h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  回测区间：<span className="font-semibold text-slate-700">{startDate} ~ {endDate}</span> · 
                  调仓周期：<span className="font-semibold text-slate-700">{rebalanceFreq}个交易日</span> (在右上角全局设置中修改)
                </p>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                {/* Mode Selector */}
                <div className="bg-slate-100 p-0.5 rounded-lg border border-slate-200 flex items-center text-xs">
                  <button
                    onClick={() => setBacktestMode('real')}
                    className={`px-3 py-1.5 rounded-md font-semibold transition-all cursor-pointer ${
                      backtestMode === 'real'
                        ? 'bg-white text-blue-700 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                    title="从本地 77.8 万条历史日线切片中逐日真实撮合选券、计算滑点印花税"
                  >
                    🔬 真实个券截面切片 (100%真实)
                  </button>
                  <button
                    onClick={() => setBacktestMode('fast')}
                    className={`px-3 py-1.5 rounded-md font-semibold transition-all cursor-pointer ${
                      backtestMode === 'fast'
                        ? 'bg-white text-blue-700 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                    title="基于真实基准走势与策略因子的快速风格推演"
                  >
                    ⚡ 因子特征快速推演
                  </button>
                </div>

                <button
                  onClick={handleRunBacktest}
                  disabled={backtestRunning || selectedStrategyIds.length === 0}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                >
                  {backtestRunning ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>{backtestMode === 'real' ? '真实个券截面撮合中...' : '并行对决模拟中...'}</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5" />
                      <span>执行对决回测</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Strategy Pill Selector */}
            <div className="flex flex-wrap gap-2 pt-1">
              {strategies.map((s) => {
                const isSelected = selectedStrategyIds.includes(s.id);
                return (
                  <button
                    key={s.id}
                    onClick={() => {
                      if (isSelected) {
                        if (selectedStrategyIds.length > 1) {
                          setSelectedStrategyIds(selectedStrategyIds.filter((id) => id !== s.id));
                        }
                      } else {
                        setSelectedStrategyIds([...selectedStrategyIds, s.id]);
                      }
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all cursor-pointer flex items-center gap-1.5 ${
                      isSelected
                        ? 'bg-blue-50 text-blue-700 border-blue-300 shadow-xs'
                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <span>{isSelected ? '✓' : '+'}</span>
                    <span>{s.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {backtestError && (
            <div className="bg-rose-50 text-rose-700 border border-rose-200 p-3 rounded-lg text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{backtestError}</span>
            </div>
          )}

          {backtestResult && (
            <div className="space-y-4">
              {/* Simulated Data Warning Banner */}
              {(() => {
                const simulatedStrats = Object.entries(backtestResult.metrics_summary)
                  .filter(([name, m]) => m.is_simulated && name !== '中证转债基准')
                  .map(([name]) => name);
                if (simulatedStrats.length === 0) return null;
                return (
                  <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-50 border border-amber-300 text-amber-800 text-xs font-medium">
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>
                      ⚠️ 数据降级警示：{simulatedStrats.length} 个策略 ({simulatedStrats.join('、')}) 因本地真实个券历史数据不足，
                      当前展示的是「因子特征推演」合成的模拟净值 (alpha/beta 参数生成)，并非真实历史撮合结果，
                      指标仅供风格参考，请勿作为实盘决策依据。前往「数据湖」完成全量历史下载后可获得真实回测。
                    </span>
                  </div>
                );
              })()}

              {/* Highlight Metrics */}
              {(() => {
                const entries = Object.entries(backtestResult.metrics_summary);
                if (entries.length === 0) return null;
                const bestCagr = [...entries].sort((a, b) => b[1].cagr - a[1].cagr)[0];
                const lowestDd = [...entries].sort((a, b) => a[1].max_drawdown - b[1].max_drawdown)[0];
                const bestSharpe = [...entries].sort((a, b) => b[1].sharpe_ratio - a[1].sharpe_ratio)[0];
                const benchmark = backtestResult.metrics_summary['中证转债基准'] || { total_return: 0 };

                return (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
                      <div className="text-[11px] text-slate-500 flex items-center gap-1">
                        <Trophy className="w-3.5 h-3.5 text-amber-500" /> 最高年化收益
                      </div>
                      <div className="text-lg font-bold text-slate-900 mt-1 truncate">
                        {bestCagr ? bestCagr[0] : '-'}
                      </div>
                      <div className="text-xs font-semibold text-emerald-600 mt-0.5">
                        +{bestCagr ? bestCagr[1].cagr : 0}% CAGR
                      </div>
                    </div>

                    <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
                      <div className="text-[11px] text-slate-500 flex items-center gap-1">
                        <Shield className="w-3.5 h-3.5 text-blue-500" /> 最低最大回撤
                      </div>
                      <div className="text-lg font-bold text-slate-900 mt-1 truncate">
                        {lowestDd ? lowestDd[0] : '-'}
                      </div>
                      <div className="text-xs font-semibold text-blue-600 mt-0.5">
                        -{lowestDd ? lowestDd[1].max_drawdown : 0}% MaxDD
                      </div>
                    </div>

                    <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
                      <div className="text-[11px] text-slate-500 flex items-center gap-1">
                        <Target className="w-3.5 h-3.5 text-purple-500" /> 最高夏普比率
                      </div>
                      <div className="text-lg font-bold text-slate-900 mt-1 truncate">
                        {bestSharpe ? bestSharpe[0] : '-'}
                      </div>
                      <div className="text-xs font-semibold text-purple-600 mt-0.5">
                        Sharpe: {bestSharpe ? bestSharpe[1].sharpe_ratio : 0}
                      </div>
                    </div>

                    <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
                      <div className="text-[11px] text-slate-500 flex items-center gap-1">
                        <BarChart3 className="w-3.5 h-3.5 text-slate-500" /> 中证转债基准收益
                      </div>
                      <div className="text-lg font-bold text-slate-900 mt-1">
                        中证转债 (000832)
                      </div>
                      <div className="text-xs font-semibold text-slate-600 mt-0.5">
                        {benchmark.total_return >= 0 ? '+' : ''}{benchmark.total_return}%
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Chart 1: Equity Curves */}
              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                <ReactECharts option={getNavChartOption()} style={{ height: '360px' }} />
              </div>

              {/* Chart 2: Drawdown */}
              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                <ReactECharts option={getDrawdownChartOption()} style={{ height: '240px' }} />
              </div>

              {/* Performance Table */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-100 font-bold text-xs text-slate-800">
                  📋 核心绩效量化指标对比表
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                      <tr>
                        <th className="py-2.5 px-4">对决策略名称</th>
                        <th className="py-2.5 px-4">年化收益 (CAGR)</th>
                        <th className="py-2.5 px-4">最大回撤 (MaxDD)</th>
                        <th className="py-2.5 px-4">夏普比率 (Sharpe)</th>
                        <th className="py-2.5 px-4">卡玛比率 (Calmar)</th>
                        <th className="py-2.5 px-4">年化波动率</th>
                        <th className="py-2.5 px-4">累计总收益</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {Object.entries(backtestResult.metrics_summary).map(([name, m]) => (
                        <tr key={name} className="hover:bg-slate-50/50">
                          <td className="py-2.5 px-4 font-semibold text-slate-800">
                            {name}
                            {m.is_simulated && (
                              <span className="ml-1.5 px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[10px] font-bold align-middle">模拟</span>
                            )}
                          </td>
                          <td className="py-2.5 px-4 text-emerald-600 font-semibold">+{m.cagr}%</td>
                          <td className="py-2.5 px-4 text-rose-600 font-semibold">-{m.max_drawdown}%</td>
                          <td className="py-2.5 px-4 text-slate-700">{m.sharpe_ratio}</td>
                          <td className="py-2.5 px-4 text-slate-700">{m.calmar_ratio}</td>
                          <td className="py-2.5 px-4 text-slate-500">{m.annual_volatility}%</td>
                          <td className="py-2.5 px-4 font-bold text-slate-900">
                            {m.total_return >= 0 ? '+' : ''}{m.total_return}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ======================================================== */}
      {/* Modal: 新建策略三步向导 (意图 → 参数 → 回测验证) */}
      {/* ======================================================== */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full border border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-3">
                <div className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
                  <Plus className="w-4 h-4 text-blue-600" />
                  <span>新建策略</span>
                </div>
                <div className="flex items-center gap-1 text-[11px] font-semibold">
                  {[{ n: 1, label: '意图' }, { n: 2, label: '参数' }, { n: 3, label: '回测验证' }].map((s) => (
                    <span key={s.n} className={`px-2 py-0.5 rounded-full ${
                      wizardStep === s.n ? 'bg-blue-600 text-white'
                      : wizardStep > s.n ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-slate-100 text-slate-400'}`}>
                      {s.n}. {s.label}
                    </span>
                  ))}
                </div>
              </div>
              <button onClick={abandonWizard} className="text-slate-400 hover:text-slate-600 p-1">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-3.5">
              {/* ---------- 第 1 步: 意图 ---------- */}
              {wizardStep === 1 && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">策略名称:</label>
                    <input
                      type="text"
                      placeholder="例如: 极低溢价博正股反弹策略"
                      value={newStratName}
                      onChange={(e) => setNewStratName(e.target.value)}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      策略逻辑阐述与适用环境 <span className="text-slate-400 font-normal">(第 2 步可交给 AI 按此描述生成参数)</span>:
                    </label>
                    <textarea
                      rows={4}
                      placeholder="说明该策略的设计哲学、防守垫与进攻收益来源。例如: 只买溢价率低于20%的低价券, 博正股反弹的弹性传导..."
                      value={newStratDesc}
                      onChange={(e) => setNewStratDesc(e.target.value)}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:border-blue-500"
                    />
                  </div>
                  <div className="pt-2 flex justify-end gap-2 border-t border-slate-100">
                    <button type="button" onClick={abandonWizard}
                      className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg">
                      取消
                    </button>
                    <button type="button"
                      onClick={() => {
                        if (!newStratName.trim()) { setWizardError('请先填写策略名称'); return; }
                        setWizardError('');
                        setWizardStep(2);
                      }}
                      className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs cursor-pointer">
                      下一步: 确定参数
                    </button>
                  </div>
                </>
              )}

              {/* ---------- 第 2 步: 参数 (手动 / AI 生成) ---------- */}
              {wizardStep === 2 && (
                <>
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-semibold text-slate-700">
                      策略参数
                      {wizardMode === 'ai' && (
                        <span className="ml-2 px-2 py-0.5 rounded text-[10px] bg-purple-100 text-purple-700">AI 已按意图生成, 可微调</span>
                      )}
                    </div>
                    <button type="button" onClick={handleWizardAiGen} disabled={wizardBusy}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-purple-50 border border-purple-200 text-purple-700 text-[11px] font-semibold hover:bg-purple-100 disabled:opacity-50 cursor-pointer">
                      ✨ {wizardBusy ? 'AI 生成中...' : (wizardMode === 'ai' ? '重新让 AI 生成' : '让 AI 按意图生成')}
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">价格下限 (元):</label>
                      <input type="number" value={newStratMinP} onChange={(e) => setNewStratMinP(Number(e.target.value))}
                        className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5" />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">价格上限 (元):</label>
                      <input type="number" value={newStratMaxP} onChange={(e) => setNewStratMaxP(Number(e.target.value))}
                        className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5" />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">规模上限 (亿元):</label>
                      <input type="number" step="0.5" value={newStratMaxScale} onChange={(e) => setNewStratMaxScale(Number(e.target.value))}
                        className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5" />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">转股溢价率上限 (%):</label>
                      <input type="number" value={newStratMaxPrem} onChange={(e) => setNewStratMaxPrem(Number(e.target.value))}
                        className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5" />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">双低权重 (W):</label>
                      <input type="number" step="0.1" value={newStratWeightDL} onChange={(e) => setNewStratWeightDL(Number(e.target.value))}
                        className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5" />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">持仓数量 (只):</label>
                      <input type="number" value={newStratTopN} onChange={(e) => setNewStratTopN(Number(e.target.value))}
                        className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5" />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-600 mb-1">核心排序规则:</label>
                    <select value={newStratSortBy} onChange={(e) => setNewStratSortBy(e.target.value)}
                      className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                      <option value="double_low">双低值 (价格 + 溢价率*W 越低越优)</option>
                      <option value="premium_rate">纯转股溢价率 (越低越优)</option>
                      <option value="price">纯价格 (贴近债底保本)</option>
                      <option value="ytm">到期收益率 YTM (越高越稳健)</option>
                    </select>
                  </div>

                  <div className="pt-2 flex justify-between items-center gap-2 border-t border-slate-100">
                    <button type="button" onClick={() => setWizardStep(1)} disabled={wizardBusy}
                      className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg disabled:opacity-50">
                      ← 返回改意图
                    </button>
                    <button type="button" onClick={runWizardPreview} disabled={wizardBusy}
                      className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs disabled:opacity-50 cursor-pointer">
                      {wizardBusy ? '回测验证中 (约需数十秒)...' : '下一步: 回测验证 →'}
                    </button>
                  </div>
                </>
              )}

              {/* ---------- 第 3 步: 回测验证 ---------- */}
              {wizardStep === 3 && (() => {
                const m = wizardPreview?.metrics_summary?.[wizardCreatedId];
                const nav = wizardPreview?.nav_series?.[wizardCreatedId] || [];
                const dates = wizardPreview?.dates || [];
                return (
                  <>
                    {m?.is_simulated && (
                      <div className="text-[11px] px-3 py-2 rounded-lg bg-amber-50 text-amber-700 border border-amber-200">
                        ⚠ 该结果来自因子模拟引擎 (非真实撮合), 仅供参考
                      </div>
                    )}
                    {m ? (
                      <>
                        <div className="grid grid-cols-4 gap-2">
                          {[
                            { label: '累计收益', val: `${m.total_return >= 0 ? '+' : ''}${m.total_return}%`, cls: m.total_return >= 0 ? 'text-emerald-600' : 'text-rose-600' },
                            { label: '年化 CAGR', val: `${m.cagr >= 0 ? '+' : ''}${m.cagr}%`, cls: m.cagr >= 0 ? 'text-emerald-600' : 'text-rose-600' },
                            { label: '最大回撤', val: `-${m.max_drawdown}%`, cls: 'text-rose-600' },
                            { label: '夏普比率', val: `${m.sharpe_ratio}`, cls: 'text-slate-800' },
                          ].map((c) => (
                            <div key={c.label} className="bg-slate-50 rounded-lg px-2 py-2 text-center">
                              <div className={`text-sm font-bold ${c.cls}`}>{c.val}</div>
                              <div className="text-[10px] text-slate-500 mt-0.5">{c.label}</div>
                            </div>
                          ))}
                        </div>
                        <div className="border border-slate-100 rounded-lg p-1">
                          <ReactECharts notMerge style={{ height: 170 }} option={{
                            grid: { left: 50, right: 12, top: 14, bottom: 24 },
                            xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 9, color: '#94a3b8' } },
                            yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 9, color: '#94a3b8' } },
                            tooltip: { trigger: 'axis', textStyle: { fontSize: 10 } },
                            series: [{
                              name: '策略净值', type: 'line', data: nav, showSymbol: false,
                              lineStyle: { width: 1.6, color: '#2563eb' },
                              areaStyle: { opacity: 0.06, color: '#2563eb' },
                            }],
                          }} />
                        </div>
                        <div className="text-[10px] text-slate-400">回测区间: 近两年 · 5 个交易日调仓 · 真实撮合模式 (T+1)</div>
                      </>
                    ) : (
                      <div className="text-xs text-slate-500 py-8 text-center">
                        近两年回测无可用结果 — 该参数区间内候选池可能为空, 建议返回放宽过滤条件
                      </div>
                    )}
                    <div className="pt-2 flex justify-between items-center gap-2 border-t border-slate-100">
                      <button type="button" onClick={abandonWizard} disabled={wizardBusy}
                        className="px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 rounded-lg disabled:opacity-50 cursor-pointer">
                        放弃并删除
                      </button>
                      <button type="button" onClick={confirmWizard} disabled={!m || wizardBusy}
                        className="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs disabled:opacity-50 cursor-pointer">
                        ✓ 验证通过, 确认入库
                      </button>
                    </div>
                  </>
                );
              })()}

              {wizardError && (
                <div className="text-xs px-3 py-2 rounded-lg bg-red-50 text-red-700">{wizardError}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* Modal: AI 探索新策略 */}
      {/* ======================================================== */}
      {isAiModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full border border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-600" />
                <span>🤖 大模型自主量化探索引擎</span>
              </div>
              <button
                onClick={() => !aiGenerating && setIsAiModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Engine Status Banner */}
              <div className="flex items-center justify-between text-xs px-3 py-2 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${llmStatus?.is_ready ? 'bg-emerald-500' : 'bg-amber-500'}`}></div>
                  <span className="text-slate-600 font-medium">当前驱动核心:</span>
                  <span className="font-bold text-slate-800">
                    {llmStatus?.is_ready 
                      ? `${llmStatus.providers?.[llmStatus.active_provider]?.name || '外部大模型'}`
                      : '本地内置自适应量化算法引擎'}
                  </span>
                </div>
                {llmStatus?.is_ready ? (
                  <span className="text-[10px] text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full font-semibold">大模型深度推理</span>
                ) : (
                  <span className="text-[10px] text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full font-semibold">启发式规则兜底</span>
                )}
              </div>

              <p className="text-xs text-slate-500">
                调用金融大模型基于市场微观博弈与异动特征，自主推演并构建全新量化策略：
              </p>

              {/* 模式选择: 参数挖掘 vs 代码进化 */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  disabled={aiGenerating}
                  onClick={() => setAiMode('discover')}
                  className={`text-left px-3 py-2 rounded-lg border text-xs transition-colors ${aiMode === 'discover' ? 'border-purple-500 bg-purple-50' : 'border-slate-200 hover:border-slate-300'} disabled:opacity-50`}
                >
                  <div className="font-bold text-slate-800">参数挖掘 <span className="text-[10px] text-slate-400">(~20秒)</span></div>
                  <div className="text-slate-500 mt-0.5">生成选券参数矩阵，走经典双低轮动框架</div>
                </button>
                <button
                  type="button"
                  disabled={aiGenerating}
                  onClick={() => setAiMode('evolve')}
                  className={`text-left px-3 py-2 rounded-lg border text-xs transition-colors ${aiMode === 'evolve' ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 hover:border-slate-300'} disabled:opacity-50`}
                >
                  <div className="font-bold text-slate-800">代码进化 <span className="text-[10px] text-amber-500">(~数分钟)</span></div>
                  <div className="text-slate-500 mt-0.5">AI 编写策略代码，沙箱+回测+评审团语义审查自动验证</div>
                </button>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  💡 给 AI 的探索灵感 (可选，留空则让 AI 自由挖掘市场规律):
                </label>
                <textarea
                  rows={3}
                  disabled={aiGenerating}
                  placeholder="例如：挖掘离回售期不足1年、价格贴近面值且大股东有强烈下修意愿的品种，专吃下修到底红利。"
                  value={aiIdea}
                  onChange={(e) => setAiIdea(e.target.value)}
                  className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:border-purple-500"
                />
                {!llmStatus?.is_ready && (
                  <p className="text-[10px] text-slate-400 mt-1">
                    💡 提示：当前未绑定外部 API Token，系统将由本地金融工程算法自适应生成策略；若需大模型深度推演，可在右上角【全局设置】中绑定 DeepSeek / 通义千问等 Token。
                  </p>
                )}
              </div>

              {aiGenerating && (
                <div className="bg-purple-50 p-3 rounded-lg border border-purple-200 flex items-center gap-3 text-xs text-purple-700 animate-pulse">
                  <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                  <span>
                    {aiMode === 'evolve'
                      ? '代码进化中: LLM 编写策略 → 沙箱安全校验 → 真实历史回测 → 体检反馈迭代 (最长数分钟，请勿关闭)...'
                      : '大模型正在推演市场微观特征，数学化生成专属参数矩阵与选券逻辑...'}
                  </span>
                </div>
              )}

              <div className="pt-2 flex justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  disabled={aiGenerating}
                  onClick={() => setIsAiModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg disabled:opacity-50"
                >
                  取消
                </button>
                <button
                  type="button"
                  disabled={aiGenerating}
                  onClick={aiMode === 'evolve' ? handleAiEvolve : handleAiDiscover}
                  className="px-4 py-2 text-xs font-semibold text-white bg-linear-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 rounded-lg shadow-xs flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
                >
                  {aiGenerating ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>{aiMode === 'evolve' ? '进化验证中...' : '正在探索...'}</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>{aiMode === 'evolve' ? '启动代码进化' : '启动深度探索与生成'}</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* Modal: AI 生成策略代码查看器 (含评审团意见) */}
      {/* ======================================================== */}
      {viewingCodeStrategy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4" onClick={() => setViewingCodeStrategy(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full border border-slate-200 max-h-[88vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-slate-100 shrink-0">
              <div>
                <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
                  AI 策略代码: {viewingCodeStrategy.name}
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">该代码在沙箱中受限执行 · 通过冒烟回测与健康体检 · 经评审团语义审查</p>
              </div>
              <button onClick={() => setViewingCodeStrategy(null)} className="text-slate-400 hover:text-slate-600 text-xl leading-none cursor-pointer">×</button>
            </div>
            <div className="overflow-y-auto p-4 space-y-4">
              <pre className="bg-slate-900 text-slate-100 text-[11px] leading-5 p-4 rounded-xl overflow-x-auto font-mono whitespace-pre">
                {viewingCodeStrategy.params?.__code__ || '// 代码缺失'}
              </pre>
              {(() => {
                const reviews = findReviewFor(viewingCodeStrategy.id);
                if (!reviews.length) return null;
                return (
                  <div className="border border-slate-200 rounded-xl p-3">
                    <div className="text-xs font-bold text-slate-700 mb-2">评审团意见</div>
                    <div className="space-y-2">
                      {reviews.map((r: any, i: number) => (
                        <div key={i} className="flex gap-2 text-xs">
                          <span className={`shrink-0 font-bold px-1.5 py-0.5 rounded text-[10px] ${r.verdict === 'pass' ? 'bg-emerald-50 text-emerald-700' : r.verdict === 'warn' ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700'}`}>
                            {r.verdict === 'pass' ? '通过' : r.verdict === 'warn' ? '提示' : '否决'}
                          </span>
                          <div>
                            <span className="font-semibold text-slate-600">{r.reviewer}: </span>
                            <span className="text-slate-500">{r.issue || '无实质问题'}</span>
                            {r.suggestion && <div className="text-slate-400 mt-0.5">建议: {r.suggestion}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}
              <div className="bg-blue-50 border border-blue-100 rounded-xl p-3 text-xs text-blue-700 flex items-start gap-2">
                <Play className="w-3.5 h-3.5 shrink-0 mt-0.5 fill-current" />
                <span>
                  下一步: 点击卡片上的「对决」进行历史回测验证 → 到「模拟锦标赛」创建账户将此策略投入实时模拟盘 → 表现稳定后可在「实盘账户」接入。
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* Modal: AI 进化实验历史 */}
      {/* ======================================================== */}
      {showExperiments && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4" onClick={() => setShowExperiments(false)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full border border-slate-200 max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-slate-100 shrink-0">
              <h3 className="font-bold text-slate-900 text-sm">AI 进化实验记录 <span className="text-slate-400 font-normal">({experiments.length})</span></h3>
              <button onClick={() => setShowExperiments(false)} className="text-slate-400 hover:text-slate-600 text-xl leading-none cursor-pointer">×</button>
            </div>
            <div className="overflow-y-auto p-4 space-y-2.5">
              {loadingExperiments ? (
                <div className="text-center text-xs text-slate-400 py-8"><RefreshCw className="w-4 h-4 animate-spin inline mr-1" />加载中...</div>
              ) : !experiments.length ? (
                <div className="text-center text-xs text-slate-400 py-8">暂无实验记录，点击「AI挖掘策略」启动代码进化</div>
              ) : experiments.map((e) => (
                <div key={e.id} className="border border-slate-200 rounded-xl p-3">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      e.status === 'succeeded' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : e.status === 'review_rejected' ? 'bg-orange-50 text-orange-700 border border-orange-200'
                      : e.status === 'health_check_failed' ? 'bg-amber-50 text-amber-700 border border-amber-200'
                      : e.status === 'sandbox_rejected' ? 'bg-red-50 text-red-700 border border-red-200'
                      : 'bg-slate-50 text-slate-600 border border-slate-200'
                    }`}>
                      {e.status === 'succeeded' ? '✓ 成功入库' : e.status === 'review_rejected' ? '评审团否决' : e.status === 'health_check_failed' ? '体检未过' : e.status === 'sandbox_rejected' ? '沙箱拦截' : e.status === 'backtest_failed' ? '回测崩溃' : '生成失败'}
                    </span>
                    <span className="text-[10px] text-slate-400">第 {e.round_idx} 轮 · {e.created_at}</span>
                    {e.strategy_name && <span className="text-xs font-semibold text-slate-700">{e.strategy_name}</span>}
                  </div>
                  <p className="text-xs text-slate-500 line-clamp-1">设想: {e.user_idea}</p>
                  {e.verdict && <p className="text-[11px] text-emerald-600 mt-1 line-clamp-2">{e.verdict}</p>}
                  {e.fail_feedback && <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">失败原因: {e.fail_feedback}</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* Modal: 策略档案与量化调优控制台 (已扩充尺寸并支持就地就近编辑) */}
      {/* ======================================================== */}
      {viewingStrategy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl xl:max-w-5xl w-full border border-slate-200 overflow-hidden my-auto flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70 shrink-0">
              <div className="flex items-center gap-3">
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                    isEditingInModal
                      ? isEditCloneMode
                        ? 'bg-blue-100 text-blue-600'
                        : 'bg-indigo-100 text-indigo-600'
                      : 'bg-blue-100 text-blue-600'
                  }`}
                >
                  {isEditingInModal ? (
                    isEditCloneMode ? (
                      <Copy className="w-4 h-4" />
                    ) : (
                      <Edit3 className="w-4 h-4" />
                    )
                  ) : (
                    <FileText className="w-4 h-4" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-bold text-base text-slate-900">
                      {isEditingInModal
                        ? isEditCloneMode
                          ? `复制微调新策略 (基于 ${viewingStrategy.name})`
                          : `修改策略参数 · ${viewingStrategy.name}`
                        : `策略详细档案 · ${viewingStrategy.name}`}
                    </h3>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        viewingStrategy.category === '系统内置'
                          ? 'bg-blue-50 text-blue-700 border border-blue-200'
                          : viewingStrategy.category?.includes('AI')
                          ? 'bg-purple-50 text-purple-700 border border-purple-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                    >
                      {isEditingInModal && isEditCloneMode
                        ? '用户自定义 (新副本)'
                        : viewingStrategy.category}
                    </span>
                    {isEditingInModal && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                        正在实时调参
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {isEditingInModal
                      ? '直接在当前窗口调整左侧投资逻辑与右侧参数矩阵，保存即可生效或直接进行对决回测'
                      : '查看该策略的量化选券哲学、因子设定及回测约束矩阵，支持一键微调或直接参战'}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  setViewingStrategy(null);
                  setIsEditingInModal(false);
                }}
                className="text-slate-400 hover:text-slate-600 p-1.5 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                title="关闭窗口"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body: Two-Column Responsive Grid */}
            <form
              onSubmit={(e) => handleSaveEdit(e, false)}
              className="flex-1 overflow-y-auto p-6 flex flex-col justify-between"
            >
              <div className="grid grid-cols-1 md:grid-cols-12 gap-6 mb-4">
                {/* Left Column (5 Cols): Strategy Info & Philosophy */}
                <div className="md:col-span-5 space-y-4">
                  {isEditingInModal ? (
                    <>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1.5 flex items-center justify-between">
                          <span>策略名称</span>
                          <span className="text-[10px] text-slate-400 font-normal">必填</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          placeholder="输入策略名称..."
                          className="w-full text-xs font-medium bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:border-blue-500 focus:bg-white transition-colors"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1.5 flex items-center justify-between">
                          <span>策略哲学与选券逻辑阐述</span>
                          <span className="text-[10px] text-slate-400 font-normal">说明核心逻辑</span>
                        </label>
                        <textarea
                          rows={7}
                          required
                          value={editDesc}
                          onChange={(e) => setEditDesc(e.target.value)}
                          placeholder="描述该策略的设计理念、选券条件及适用行情..."
                          className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:border-blue-500 focus:bg-white transition-colors leading-relaxed"
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <div className="text-xs font-bold text-slate-600 mb-1.5 flex items-center gap-1.5">
                          <Target className="w-3.5 h-3.5 text-blue-600" />
                          <span>投资哲学与选券逻辑</span>
                        </div>
                        <div className="bg-slate-50/80 p-4 rounded-xl border border-slate-100 text-xs text-slate-700 leading-relaxed min-h-[140px]">
                          {viewingStrategy.description}
                        </div>
                      </div>

                      <div className="bg-blue-50/60 border border-blue-100 rounded-xl p-3.5 text-xs text-blue-900 space-y-1">
                        <div className="font-semibold flex items-center gap-1.5 text-blue-800">
                          <Shield className="w-3.5 h-3.5 text-blue-600" />
                          <span>本地数据湖回测撮合规则</span>
                        </div>
                        <p className="text-[11px] text-blue-700 leading-relaxed">
                          该策略挂载于本地 77.8 万条历史日线切片中。在对决竞技场中将根据调仓周期进行实时截面撮合、滑点与佣金计算。
                        </p>
                      </div>
                    </>
                  )}
                </div>

                {/* Right Column (7 Cols): Quantitative Parameters Matrix */}
                <div className="md:col-span-7 space-y-3">
                  <div className="text-xs font-bold text-slate-600 mb-1.5 flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <BarChart3 className="w-3.5 h-3.5 text-indigo-600" />
                      <span>专属量化参数配置矩阵</span>
                    </div>
                    {isEditingInModal && (
                      <span className="text-[11px] text-blue-600 font-normal">
                        可直接修改下方数值
                      </span>
                    )}
                  </div>

                  {isEditingInModal ? (
                    <div className="space-y-3.5">
                      {/* 1. 价格区间 */}
                      <div className="bg-slate-50/70 p-3 rounded-xl border border-slate-200/80">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-xs font-bold text-slate-700">价格区间 (元)</span>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => { setEditMinP(90); setEditMaxP(110); }}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-600 hover:text-blue-600 border border-slate-200 cursor-pointer"
                            >
                              纯债保本(90~110)
                            </button>
                            <button
                              type="button"
                              onClick={() => { setEditMinP(95); setEditMaxP(125); }}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-600 hover:text-blue-600 border border-slate-200 cursor-pointer"
                            >
                              经典双低(95~125)
                            </button>
                            <button
                              type="button"
                              onClick={() => { setEditMinP(110); setEditMaxP(140); }}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-600 hover:text-blue-600 border border-slate-200 cursor-pointer"
                            >
                              进攻弹性(110~140)
                            </button>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                              <span>下限: <b className="text-slate-800">{editMinP}元</b></span>
                            </div>
                            <input
                              type="range"
                              min="70"
                              max="140"
                              step="1"
                              value={editMinP}
                              onChange={(e) => setEditMinP(Number(e.target.value))}
                              className="w-full accent-blue-600 h-1.5 bg-slate-200 rounded-lg cursor-pointer"
                            />
                          </div>
                          <div>
                            <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                              <span>上限: <b className="text-slate-800">{editMaxP}元</b></span>
                            </div>
                            <input
                              type="range"
                              min="90"
                              max="180"
                              step="1"
                              value={editMaxP}
                              onChange={(e) => setEditMaxP(Number(e.target.value))}
                              className="w-full accent-blue-600 h-1.5 bg-slate-200 rounded-lg cursor-pointer"
                            />
                          </div>
                        </div>
                      </div>

                      {/* 2. 规模上限 & 溢价率上限 */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-slate-50/70 p-3 rounded-xl border border-slate-200/80">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-slate-700">规模上限</span>
                            <span className="text-xs font-bold text-blue-600">&le; {editMaxScale} 亿元</span>
                          </div>
                          <div className="flex items-center gap-1 mb-2">
                            <button
                              type="button"
                              onClick={() => setEditMaxScale(3.0)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-600 hover:text-blue-600 border border-slate-200 cursor-pointer"
                            >
                              &le;3亿(小妖)
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditMaxScale(5.0)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-600 hover:text-blue-600 border border-slate-200 cursor-pointer"
                            >
                              &le;5亿(均衡)
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditMaxScale(10.0)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-blue-50 text-slate-600 hover:text-blue-600 border border-slate-200 cursor-pointer"
                            >
                              &le;10亿(大盘)
                            </button>
                          </div>
                          <input
                            type="range"
                            min="1"
                            max="20"
                            step="0.5"
                            value={editMaxScale}
                            onChange={(e) => setEditMaxScale(Number(e.target.value))}
                            className="w-full accent-blue-600 h-1.5 bg-slate-200 rounded-lg cursor-pointer"
                          />
                        </div>

                        <div className="bg-slate-50/70 p-3 rounded-xl border border-slate-200/80">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-slate-700">溢价率上限</span>
                            <span className="text-xs font-bold text-indigo-600">&le; {editMaxPrem}%</span>
                          </div>
                          <div className="flex items-center gap-1 mb-2">
                            <button
                              type="button"
                              onClick={() => setEditMaxPrem(30)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-indigo-50 text-slate-600 hover:text-indigo-600 border border-slate-200 cursor-pointer"
                            >
                              &le;30%(强攻)
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditMaxPrem(50)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-indigo-50 text-slate-600 hover:text-indigo-600 border border-slate-200 cursor-pointer"
                            >
                              &le;50%(均衡)
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditMaxPrem(75)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-indigo-50 text-slate-600 hover:text-indigo-600 border border-slate-200 cursor-pointer"
                            >
                              &le;75%(宽幅)
                            </button>
                          </div>
                          <input
                            type="range"
                            min="10"
                            max="120"
                            step="1"
                            value={editMaxPrem}
                            onChange={(e) => setEditMaxPrem(Number(e.target.value))}
                            className="w-full accent-indigo-600 h-1.5 bg-slate-200 rounded-lg cursor-pointer"
                          />
                        </div>
                      </div>

                      {/* 3. 双低权重 W & 目标持仓 */}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-slate-50/70 p-3 rounded-xl border border-slate-200/80">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-slate-700">双低权重 W</span>
                            <span className="text-xs font-bold text-slate-800">{editWeightDL}</span>
                          </div>
                          <div className="flex items-center gap-1 mb-2">
                            <button
                              type="button"
                              onClick={() => setEditWeightDL(0.8)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-slate-100 text-slate-600 border border-slate-200 cursor-pointer"
                            >
                              0.8 偏价格
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditWeightDL(1.0)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-slate-100 text-slate-600 border border-slate-200 cursor-pointer"
                            >
                              1.0 经典
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditWeightDL(1.2)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-slate-100 text-slate-600 border border-slate-200 cursor-pointer"
                            >
                              1.2 偏弹性
                            </button>
                          </div>
                          <input
                            type="range"
                            min="0.2"
                            max="2.5"
                            step="0.1"
                            value={editWeightDL}
                            onChange={(e) => setEditWeightDL(Number(e.target.value))}
                            className="w-full accent-slate-700 h-1.5 bg-slate-200 rounded-lg cursor-pointer"
                          />
                        </div>

                        <div className="bg-slate-50/70 p-3 rounded-xl border border-slate-200/80">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-slate-700">目标持仓</span>
                            <span className="text-xs font-bold text-emerald-700">{editTopN} 只</span>
                          </div>
                          <div className="flex items-center gap-1 mb-2">
                            <button
                              type="button"
                              onClick={() => setEditTopN(5)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-emerald-50 text-slate-600 hover:text-emerald-700 border border-slate-200 cursor-pointer"
                            >
                              5只 集中
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditTopN(10)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-emerald-50 text-slate-600 hover:text-emerald-700 border border-slate-200 cursor-pointer"
                            >
                              10只 均衡
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditTopN(15)}
                              className="text-[10px] px-1 py-0.5 rounded bg-white hover:bg-emerald-50 text-slate-600 hover:text-emerald-700 border border-slate-200 cursor-pointer"
                            >
                              15只 分散
                            </button>
                          </div>
                          <input
                            type="range"
                            min="3"
                            max="30"
                            step="1"
                            value={editTopN}
                            onChange={(e) => setEditTopN(Number(e.target.value))}
                            className="w-full accent-emerald-600 h-1.5 bg-slate-200 rounded-lg cursor-pointer"
                          />
                        </div>
                      </div>

                      {/* 4. 核心选券排序因子 (视觉选择卡) */}
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1.5">
                          核心选券排序因子
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                          {[
                            { id: 'double_low', name: '双低值', desc: '价格 + 溢价率×W · 兼顾保本与弹性', icon: '🎯' },
                            { id: 'premium_rate', name: '纯溢价率', desc: '转股溢价率升序 · 专抓正股高爆发', icon: '🚀' },
                            { id: 'price', name: '纯价格', desc: '转债价格升序 · 贴近纯债底强防守', icon: '🛡️' },
                            { id: 'ytm', name: '到期收益率', desc: 'YTM降序 · 稳健吃息纯债底', icon: '💰' },
                          ].map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => setEditSortBy(item.id)}
                              className={`p-2 rounded-xl border text-left transition-all cursor-pointer ${
                                editSortBy === item.id
                                  ? 'bg-blue-50/80 border-blue-400 shadow-2xs'
                                  : 'bg-slate-50 border-slate-200 hover:bg-slate-100/70'
                              }`}
                            >
                              <div className="flex items-center gap-1.5 font-bold text-xs text-slate-800">
                                <span>{item.icon}</span>
                                <span>{item.name}</span>
                                {editSortBy === item.id && (
                                  <span className="text-[10px] text-blue-600 font-semibold ml-auto">✓ 选中</span>
                                )}
                              </div>
                              <div className="text-[10px] text-slate-400 mt-0.5 truncate">{item.desc}</div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex flex-col justify-between">
                        <span className="text-slate-400 text-[11px]">价格区间</span>
                        <span className="font-bold text-slate-800 text-sm mt-1">
                          {viewingStrategy.params.min_price} ~ {viewingStrategy.params.max_price}{' '}
                          <span className="text-xs font-normal text-slate-500">元</span>
                        </span>
                      </div>
                      <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex flex-col justify-between">
                        <span className="text-slate-400 text-[11px]">规模上限</span>
                        <span className="font-bold text-slate-800 text-sm mt-1">
                          &le; {viewingStrategy.params.max_scale}{' '}
                          <span className="text-xs font-normal text-slate-500">亿元</span>
                        </span>
                      </div>
                      <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex flex-col justify-between">
                        <span className="text-slate-400 text-[11px]">溢价率上限</span>
                        <span className="font-bold text-slate-800 text-sm mt-1">
                          &le; {viewingStrategy.params.max_premium}{' '}
                          <span className="text-xs font-normal text-slate-500">%</span>
                        </span>
                      </div>
                      <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex flex-col justify-between">
                        <span className="text-slate-400 text-[11px]">双低权重 W</span>
                        <span className="font-bold text-slate-800 text-sm mt-1">
                          {viewingStrategy.params.double_low_weight || 1.0}
                        </span>
                      </div>
                      <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex flex-col justify-between">
                        <span className="text-slate-400 text-[11px]">持仓只数</span>
                        <span className="font-bold text-slate-800 text-sm mt-1">
                          {viewingStrategy.params.top_n}{' '}
                          <span className="text-xs font-normal text-slate-500">只</span>
                        </span>
                      </div>
                      <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex flex-col justify-between">
                        <span className="text-slate-400 text-[11px]">核心排序</span>
                        <span className="font-bold text-slate-800 text-sm mt-1">
                          {viewingStrategy.params.sort_by === 'double_low'
                            ? '双低值'
                            : viewingStrategy.params.sort_by === 'premium_rate'
                            ? '溢价率'
                            : viewingStrategy.params.sort_by === 'price'
                            ? '纯价格'
                            : viewingStrategy.params.sort_by === 'ytm'
                            ? '到期收益率'
                            : viewingStrategy.params.sort_by}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Modal Footer: Balanced Single-Row Layout */}
              <div className="pt-4 border-t border-slate-100 flex items-center justify-between gap-3 shrink-0">
                {isEditingInModal ? (
                  <>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setIsEditingInModal(false)}
                        className="px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer whitespace-nowrap"
                      >
                        取消编辑
                      </button>
                    </div>

                    <div className="flex items-center gap-2.5">
                      <button
                        type="button"
                        onClick={(e) => handleSaveEdit(e, false)}
                        className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg shadow-2xs transition-colors cursor-pointer whitespace-nowrap"
                      >
                        <Save className="w-3.5 h-3.5 text-slate-600" />
                        <span>{isEditCloneMode ? '保存为新版本' : '保存修改'}</span>
                      </button>

                      <button
                        type="button"
                        onClick={(e) => handleSaveEdit(e, true)}
                        className="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-linear-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 rounded-lg shadow-sm hover:shadow transition-all cursor-pointer whitespace-nowrap"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>保存并立即进入对决回测</span>
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    {/* Left: Strategy Management Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => startEditingCurrent(true)}
                        className="inline-flex items-center gap-1.5 bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-600 text-xs font-semibold px-3.5 py-2 rounded-lg border border-slate-200 hover:border-blue-200 transition-all shadow-2xs cursor-pointer whitespace-nowrap"
                        title="以此策略为蓝本，复制一份并微调参数"
                      >
                        <Copy className="w-3.5 h-3.5 text-blue-500" />
                        <span>复制微调为新版本</span>
                      </button>

                      {viewingStrategy.category !== '系统内置' && (
                        <button
                          type="button"
                          onClick={() => startEditingCurrent(false)}
                          className="inline-flex items-center gap-1.5 bg-white hover:bg-indigo-50 text-slate-700 hover:text-indigo-600 text-xs font-semibold px-3.5 py-2 rounded-lg border border-slate-200 hover:border-indigo-200 transition-all shadow-2xs cursor-pointer whitespace-nowrap"
                          title="直接在当前窗口修改本策略参数"
                        >
                          <Edit3 className="w-3.5 h-3.5 text-indigo-500" />
                          <span>直接修改参数</span>
                        </button>
                      )}
                    </div>

                    {/* Right: Close & Primary CTA */}
                    <div className="flex items-center gap-2.5">
                      <button
                        type="button"
                        onClick={() => setViewingStrategy(null)}
                        className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer whitespace-nowrap"
                      >
                        关闭
                      </button>

                      {onSendToAgent && (
                        <button
                          type="button"
                          onClick={() => {
                            onSendToAgent(viewingStrategy.id);
                            setViewingStrategy(null);
                          }}
                          className="inline-flex items-center gap-1.5 bg-linear-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm hover:shadow transition-all cursor-pointer whitespace-nowrap"
                          title="以此策略为标的初筛池，立即移交今日AI智能体会议室进行多空会诊"
                        >
                          <Bot className="w-3.5 h-3.5" />
                          <span>送交今日AI投委会会诊</span>
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={() => {
                          setSelectedStrategyIds((prev) =>
                            Array.from(new Set([...prev, viewingStrategy.id]))
                          );
                          setViewingStrategy(null);
                          setSubView('arena');
                        }}
                        className="inline-flex items-center gap-2 bg-linear-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-semibold px-5 py-2 rounded-lg shadow-sm hover:shadow transition-all cursor-pointer whitespace-nowrap"
                        title="将此策略加入对决阵容并切换到对决竞技场"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>加入对决回测</span>
                      </button>
                    </div>
                  </>
                )}
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
