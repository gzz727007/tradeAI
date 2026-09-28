import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { Account, Strategy, PaperNavHistoryResponse, PositionItem } from '../types';
import { api } from '../api/client';
import {
  Gamepad2,
  TrendingUp,
  DollarSign,
  Briefcase,
  Info,
  RefreshCw,
  Play,
  Pause,
  Square,
  RotateCcw,
  Zap,
  Plus,
  Trash2,
  ArrowUpRight,
  ArrowDownRight,
  Award,
  ShieldCheck,
  Activity,
  BarChart3,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  Layers,
  History,
  TrendingDown
} from 'lucide-react';

export const PaperTournament: React.FC = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccId, setSelectedAccId] = useState<string>('');
  const [navDetail, setNavDetail] = useState<PaperNavHistoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [rebalancing, setRebalancing] = useState<boolean>(false);

  // 视图控制
  const [chartMode, setChartMode] = useState<'return' | 'nav'>('return');
  const [timeRange, setTimeRange] = useState<'1W' | '1M' | '3M' | 'ALL'>('ALL');
  const [activeTab, setActiveTab] = useState<'positions' | 'trades'>('positions');

  // 新建模拟盘弹窗
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [newAccName, setNewAccName] = useState<string>('');
  const [newAccStrategy, setNewAccStrategy] = useState<string>('');
  const [newAccCapital, setNewAccCapital] = useState<number>(100000);
  const [newAccAutoSeed, setNewAccAutoSeed] = useState<boolean>(true);

  // 消息提示
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  const showToast = (type: 'success' | 'error' | 'info', message: string) => {
    setNotification({ type, message });
    setTimeout(() => {
      setNotification(null);
    }, 4500);
  };

  // 加载所有模拟账户列表
  const loadPaperAccounts = async (preferredId?: string) => {
    setLoading(true);
    try {
      const data = await api.getAccounts('PAPER');
      setAccounts(data);
      const targetId = preferredId || selectedAccId || (data.length > 0 ? data[0].account_id : '');
      if (targetId) {
        setSelectedAccId(targetId);
        loadAccountDetail(targetId);
      }
    } catch (err: any) {
      showToast('error', err.message || '加载模拟账户失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载选定账户的净值历史、基准走势与指标
  const loadAccountDetail = async (accountId: string) => {
    if (!accountId) return;
    setDetailLoading(true);
    try {
      const detail = await api.getPaperNavHistory(accountId);
      setNavDetail(detail);
    } catch (err: any) {
      console.error(err);
      showToast('error', err.message || '获取净值曲线失败');
    } finally {
      setDetailLoading(false);
    }
  };

  // 加载可选策略列表
  const loadStrategies = async () => {
    try {
      const list = await api.getStrategies();
      setStrategies(list);
      if (list.length > 0 && !newAccStrategy) {
        setNewAccStrategy(list[0].name);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadPaperAccounts();
    loadStrategies();
  }, []);

  const handleSelectAccount = (accId: string) => {
    setSelectedAccId(accId);
    loadAccountDetail(accId);
  };

  // 启动模拟赛马
  const handleStart = async () => {
    if (!selectedAccId) return;
    setActionLoading(true);
    try {
      await api.startPaperAccount(selectedAccId);
      showToast('success', '模拟赛马已启动，进入持续前向跟踪状态！');
      loadPaperAccounts(selectedAccId);
    } catch (err: any) {
      showToast('error', err.message || '启动失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 暂停模拟赛马
  const handlePause = async () => {
    if (!selectedAccId) return;
    setActionLoading(true);
    try {
      await api.pausePaperAccount(selectedAccId);
      showToast('info', '模拟赛马已暂停');
      loadPaperAccounts(selectedAccId);
    } catch (err: any) {
      showToast('error', err.message || '暂停失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 结束模拟赛马
  const handleEnd = async () => {
    if (!selectedAccId) return;
    if (!window.confirm('确认结束并归档该模拟盘赛马吗？结束后将停止自动调仓。')) return;
    setActionLoading(true);
    try {
      await api.endPaperAccount(selectedAccId);
      showToast('info', '模拟赛马已结束归档');
      loadPaperAccounts(selectedAccId);
    } catch (err: any) {
      showToast('error', err.message || '结束失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 立即触发模拟调仓
  const handleRebalance = async () => {
    if (!selectedAccId) return;
    setRebalancing(true);
    try {
      const res = await api.rebalancePaperAccount(selectedAccId);
      showToast(
        'success',
        `调仓完成！卖出 ${res.sold_count} 只移出标的，新买入 ${res.bought_count} 只策略领先标的，最新资产已结算。`
      );
      await loadPaperAccounts(selectedAccId);
      await loadAccountDetail(selectedAccId);
    } catch (err: any) {
      showToast('error', err.message || '调仓执行失败');
    } finally {
      setRebalancing(false);
    }
  };

  // 补齐 60 天真实历史轨迹
  const handleSeedHistory = async () => {
    if (!selectedAccId) return;
    setActionLoading(true);
    try {
      await api.seedPaperHistory(selectedAccId, 60);
      showToast('success', '已基于真实可转债数据湖成功预演补齐近 60 个交易日前向轨迹！');
      await loadPaperAccounts(selectedAccId);
      await loadAccountDetail(selectedAccId);
    } catch (err: any) {
      showToast('error', err.message || '补齐轨迹失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 重置模拟盘
  const handleReset = async () => {
    if (!selectedAccId) return;
    if (
      !window.confirm(
        '确定要重置该模拟盘吗？将清空该账户所有历史调仓流水与持仓，可用资金恢复至初始金额。'
      )
    ) {
      return;
    }
    setActionLoading(true);
    try {
      await api.resetPaperAccount(selectedAccId);
      showToast('success', '账户已成功重置为初始资金状态！');
      await loadPaperAccounts(selectedAccId);
      await loadAccountDetail(selectedAccId);
    } catch (err: any) {
      showToast('error', err.message || '重置失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 删除模拟盘
  const handleDeleteAccount = async () => {
    if (!selectedAccId) return;
    if (!window.confirm('确定要删除该模拟盘账户吗？此操作无法撤销。')) return;
    setActionLoading(true);
    try {
      await api.deletePaperAccount(selectedAccId);
      showToast('success', '模拟账户已删除');
      const remaining = accounts.filter((a) => a.account_id !== selectedAccId);
      setAccounts(remaining);
      const nextId = remaining.length > 0 ? remaining[0].account_id : '';
      setSelectedAccId(nextId);
      if (nextId) loadAccountDetail(nextId);
      else setNavDetail(null);
    } catch (err: any) {
      showToast('error', err.message || '删除失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 创建新模拟盘
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAccName.trim()) {
      showToast('error', '请输入模拟盘名称');
      return;
    }
    setActionLoading(true);
    const newId = `paper_${Date.now()}`;
    try {
      await api.createAccount({
        account_id: newId,
        account_name: newAccName,
        associated_strategy: newAccStrategy,
        account_type: 'PAPER',
        initial_capital: newAccCapital,
        auto_seed: newAccAutoSeed,
      });
      showToast('success', `模拟赛马账户【${newAccName}】创建成功！`);
      setIsModalOpen(false);
      setNewAccName('');
      await loadPaperAccounts(newId);
    } catch (err: any) {
      showToast('error', err.message || '创建模拟盘失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 过滤曲线时序数据
  const rawCurve = navDetail?.curve_data || [];
  const getFilteredCurve = () => {
    if (!rawCurve.length) return [];
    let sliceLen = rawCurve.length;
    if (timeRange === '1W') sliceLen = 6;
    else if (timeRange === '1M') sliceLen = 22;
    else if (timeRange === '3M') sliceLen = 66;

    const sliced = rawCurve.slice(-sliceLen);
    return sliced.map((item) => ({
      date: item.date,
      strategy_nav: Number(item.nav?.toFixed(4) || 1.0),
      benchmark_nav: Number(item.benchmark_nav?.toFixed(4) || 1.0),
      strategy_return: Number(
        (item.portfolio_return !== undefined
          ? item.portfolio_return
          : (item.nav - 1.0) * 100
        ).toFixed(2)
      ),
      benchmark_return: Number(
        (item.benchmark_return !== undefined
          ? item.benchmark_return
          : ((item.benchmark_nav || 1.0) - 1.0) * 100
        ).toFixed(2)
      ),
      excess_return: Number(
        (item.excess_return !== undefined
          ? item.excess_return
          : ((item.portfolio_return || 0) - (item.benchmark_return || 0))
        ).toFixed(2)
      ),
      total_assets: item.total_assets,
    }));
  };

  const chartData = getFilteredCurve();
  const curAcc = accounts.find((a) => a.account_id === selectedAccId) || accounts[0];
  const metrics = navDetail?.metrics;
  const isRunning = curAcc?.status === 'RUNNING' || curAcc?.status === 'ACTIVE';
  const isPaused = curAcc?.status === 'PAUSED';
  const isEnded = curAcc?.status === 'ENDED';

  // ECharts Option
  const getChartOption = () => {
    if (!chartData.length) return {};
    const dates = chartData.map((d) => d.date);
    const stratSeries = chartData.map((d) => (chartMode === 'return' ? d.strategy_return : d.strategy_nav));
    const benchSeries = chartData.map((d) => (chartMode === 'return' ? d.benchmark_return : d.benchmark_nav));

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any) => {
          if (!params || !params.length) return '';
          const idx = params[0].dataIndex;
          const p = chartData[idx];
          if (!p) return '';
          return `
            <div style="font-size:12px; line-height:1.6; min-width:190px; color:#1e293b;">
              <div style="font-weight:bold; border-bottom:1px solid #e2e8f0; margin-bottom:5px; padding-bottom:3px; display:flex; justify-content:space-between;">
                <span>${p.date}</span>
                <span style="color:#4f46e5;">¥${p.total_assets ? p.total_assets.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : ''}</span>
              </div>
              <div style="display:flex; justify-content:space-between; color:#4f46e5;">
                <span>● 策略表现:</span>
                <b>${chartMode === 'return' ? (p.strategy_return > 0 ? '+' : '') + p.strategy_return + '%' : p.strategy_nav}</b>
              </div>
              <div style="display:flex; justify-content:space-between; color:#d97706;">
                <span>● 中证转债:</span>
                <b>${chartMode === 'return' ? (p.benchmark_return > 0 ? '+' : '') + p.benchmark_return + '%' : p.benchmark_nav}</b>
              </div>
              <div style="display:flex; justify-content:space-between; color:#059669; border-top:1px dashed #cbd5e1; margin-top:5px; padding-top:3px;">
                <span>● 超额Alpha:</span>
                <b>${p.excess_return > 0 ? '+' : ''}${p.excess_return}%</b>
              </div>
            </div>
          `;
        },
      },
      legend: {
        bottom: 0,
        textStyle: { fontSize: 11, color: '#64748b' },
      },
      grid: {
        top: 20,
        left: 55,
        right: 25,
        bottom: 35,
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          formatter: (val: string) => val.slice(5),
        },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        splitLine: { lineStyle: { color: '#f1f5f9' } },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          formatter: (val: number) => (chartMode === 'return' ? `${val}%` : val.toFixed(3)),
        },
      },
      series: [
        {
          name: curAcc?.associated_strategy || '模拟赛马策略',
          type: 'line',
          data: stratSeries,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2.5, color: '#6366f1' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(99, 102, 241, 0.22)' },
                { offset: 1, color: 'rgba(99, 102, 241, 0.01)' },
              ],
            },
          },
        },
        {
          name: '中证转债基准 (sh000832)',
          type: 'line',
          data: benchSeries,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.8, color: '#f59e0b', type: 'dashed' },
        },
      ],
    };
  };

  return (
    <div className="space-y-5">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`p-3.5 rounded-xl border text-xs font-semibold flex items-center justify-between shadow-md transition-all animate-fadeIn ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : notification.type === 'error'
              ? 'bg-rose-50 text-rose-800 border-rose-200'
              : 'bg-indigo-50 text-indigo-800 border-indigo-200'
          }`}
        >
          <div className="flex items-center gap-2">
            {notification.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-600" />}
            {notification.type === 'error' && <AlertTriangle className="w-4 h-4 text-rose-600" />}
            {notification.type === 'info' && <Info className="w-4 h-4 text-indigo-600" />}
            <span>{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-slate-400 hover:text-slate-600 text-sm ml-3 font-bold"
          >
            ×
          </button>
        </div>
      )}

      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-5 rounded-2xl border border-slate-800 shadow-md flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="p-2 bg-indigo-500/20 text-indigo-400 rounded-xl border border-indigo-500/30">
              <Gamepad2 className="w-5 h-5" />
            </span>
            <div>
              <h2 className="text-base font-bold tracking-tight">
                实盘模拟赛马竞技场 (Forward Paper Trading Sandbox)
              </h2>
              <p className="text-xs text-slate-300 mt-0.5">
                全真实行情的“前向赛马”竞技！策略独立账户每日模拟自动选券、调仓并推演真实净值走势，对比中证转债基准，零真金白银风险。
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-3.5 py-2 rounded-xl transition-all shadow-sm hover:shadow cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>新建赛马账户</span>
          </button>
          <button
            onClick={() => loadPaperAccounts()}
            disabled={loading}
            className="flex items-center gap-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs font-semibold px-3 py-2 rounded-xl border border-slate-700 transition-all cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>刷新行情估值</span>
          </button>
        </div>
      </div>

      {/* Loading Skeleton State (极速骨架屏，避免白屏等待) */}
      {loading && accounts.length === 0 && (
        <div className="space-y-4 animate-pulse">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3.5">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-3">
                <div className="flex justify-between items-center">
                  <div className="h-4 bg-slate-200 rounded w-28"></div>
                  <div className="h-4 bg-slate-100 rounded w-16"></div>
                </div>
                <div className="h-7 bg-slate-200 rounded w-36"></div>
                <div className="flex justify-between pt-2 border-t border-slate-100">
                  <div className="h-3 bg-slate-100 rounded w-20"></div>
                  <div className="h-3 bg-slate-100 rounded w-16"></div>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-2xs text-center py-12 space-y-3">
            <RefreshCw className="w-7 h-7 text-indigo-500 animate-spin mx-auto" />
            <div className="text-xs font-bold text-slate-700">正在极速加载模拟赛马账户与净值曲线...</div>
            <div className="text-[11px] text-slate-400">正在对接真实行情数据湖并完成持仓每日估值</div>
          </div>
        </div>
      )}

      {/* Empty State (无模拟盘时的指引卡片) */}
      {!loading && accounts.length === 0 && (
        <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-sm text-center py-16 space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mx-auto">
            <Gamepad2 className="w-8 h-8" />
          </div>
          <div>
            <h3 className="font-bold text-base text-slate-800">暂无正在运行的实盘模拟赛马账户</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              模拟赛马可让您的量化策略在前向真实行情中每日自动选券、调仓并推演真实净值走势，对比中证转债基准，零真金白银风险！
            </p>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-5 py-2.5 rounded-xl shadow-xs hover:shadow transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>立即创建第一个赛马账户</span>
          </button>
        </div>
      )}

      {/* Account Cards Grid (赛马选手卡片列表) */}
      {accounts.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3.5">
          {accounts.map((acc) => {
            const isSelected = acc.account_id === selectedAccId;
            const latestNav = acc.nav_history?.[acc.nav_history.length - 1];
            const totalAssets = latestNav?.total_assets || acc.total_asset || acc.initial_capital;
            const navValue = latestNav?.nav || totalAssets / acc.initial_capital;
            const profitPct = Math.round((navValue - 1.0) * 10000) / 100;
            const status = acc.status || 'ACTIVE';

            let statusBadge = (
              <span className="inline-flex items-center gap-1 text-[11px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full font-semibold border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                赛马运行中
              </span>
            );
            if (status === 'PAUSED') {
              statusBadge = (
                <span className="inline-flex items-center gap-1 text-[11px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full font-semibold border border-amber-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                  已暂停
                </span>
              );
            } else if (status === 'ENDED') {
              statusBadge = (
                <span className="inline-flex items-center gap-1 text-[11px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-semibold border border-slate-300">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
                  已归档
                </span>
              );
            } else if (status === 'IDLE') {
              statusBadge = (
                <span className="inline-flex items-center gap-1 text-[11px] bg-slate-50 text-slate-500 px-2 py-0.5 rounded-full font-semibold border border-slate-200">
                  未启动
                </span>
              );
            }

            return (
              <div
                key={acc.account_id}
                onClick={() => handleSelectAccount(acc.account_id)}
                className={`bg-white p-4 rounded-xl border transition-all cursor-pointer relative ${
                  isSelected
                    ? 'border-indigo-600 shadow-md ring-2 ring-indigo-500/15'
                    : 'border-slate-200 hover:border-slate-300 hover:shadow-xs'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="font-bold text-xs text-slate-900 truncate max-w-[150px]">
                    {acc.account_name}
                  </div>
                  {statusBadge}
                </div>

                <div className="flex items-baseline justify-between mb-1.5">
                  <span className="text-xl font-extrabold text-slate-900">
                    ¥{totalAssets.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                  <span
                    className={`text-xs font-bold flex items-center ${
                      profitPct >= 0 ? 'text-emerald-600' : 'text-rose-600'
                    }`}
                  >
                    {profitPct >= 0 ? <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" /> : <ArrowDownRight className="w-3.5 h-3.5 mr-0.5" />}
                    {profitPct >= 0 ? '+' : ''}
                    {profitPct.toFixed(2)}%
                  </span>
                </div>

                <div className="flex justify-between text-[11px] text-slate-500 pt-2 border-t border-slate-100">
                  <span>
                    当前净值: <b className="text-slate-800">{navValue.toFixed(4)}</b>
                  </span>
                  <span>
                    现金: <b className="text-slate-800">¥{acc.available_cash.toLocaleString()}</b>
                  </span>
                </div>

                <div className="mt-2 text-[10px] text-slate-500 truncate flex items-center justify-between">
                  <span className="truncate">
                    策略: <b className="text-indigo-600">{acc.associated_strategy}</b>
                  </span>
                  <span className="text-slate-400">
                    {acc.nav_history?.length || 0} 跟踪日
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Selected Account Deep Dashboard */}
      {curAcc && accounts.length > 0 && (
        <div className="space-y-4">
          {/* Action Control Bar (启动 / 暂停 / 结束 / 调仓 / 重置) */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold">
                <Award className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-sm text-slate-900">{curAcc.account_name}</h3>
                  <span className="text-[11px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded font-medium border border-indigo-200">
                    绑定: {curAcc.associated_strategy}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  初始资金: ¥{curAcc.initial_capital.toLocaleString()} | 累计调仓: {navDetail?.metrics?.rebalance_count || 0} 次 | 运行跟踪天数: {navDetail?.metrics?.trading_days || 0} 天
                </p>
              </div>
            </div>

            {/* Lifecycle Action Buttons */}
            <div className="flex items-center flex-wrap gap-2">
              {isRunning ? (
                <button
                  onClick={handlePause}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                >
                  <Pause className="w-3.5 h-3.5" />
                  <span>暂停赛马</span>
                </button>
              ) : (
                <button
                  onClick={handleStart}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition-all shadow-xs cursor-pointer"
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>启动赛马</span>
                </button>
              )}

              <button
                onClick={handleRebalance}
                disabled={rebalancing}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-all shadow-xs cursor-pointer"
              >
                <Zap className={`w-3.5 h-3.5 ${rebalancing ? 'animate-bounce' : ''}`} />
                <span>{rebalancing ? '正在计算选券调仓...' : '立即模拟调仓'}</span>
              </button>

              <button
                onClick={handleSeedHistory}
                disabled={actionLoading}
                title="基于真实可转债数据湖预演补齐近60天真实净值走势"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-medium transition-colors cursor-pointer"
              >
                <History className="w-3.5 h-3.5 text-indigo-600" />
                <span>补齐60天轨迹</span>
              </button>

              {!isEnded && (
                <button
                  onClick={handleEnd}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                >
                  <Square className="w-3.5 h-3.5" />
                  <span>完结归档</span>
                </button>
              )}

              <button
                onClick={handleReset}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-slate-600 hover:text-amber-700 hover:bg-amber-50 rounded-lg text-xs font-medium transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>重置资金</span>
              </button>

              <button
                onClick={handleDeleteAccount}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                title="删除该模拟盘"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* KPI Performance Metrics Cards (量化核心战报) */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5 text-indigo-500" />
                累计收益率
              </span>
              <div
                className={`text-base font-extrabold mt-1 ${
                  (metrics?.total_return || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'
                }`}
              >
                {(metrics?.total_return || 0) >= 0 ? '+' : ''}
                {(metrics?.total_return || 0).toFixed(2)}%
              </div>
              <span className="text-[10px] text-slate-400">
                最新净值: {chartData.length ? chartData[chartData.length - 1].strategy_nav.toFixed(4) : '1.0000'}
              </span>
            </div>

            <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                <BarChart3 className="w-3.5 h-3.5 text-amber-500" />
                基准(中证转债)
              </span>
              <div
                className={`text-base font-extrabold mt-1 ${
                  (metrics?.benchmark_return || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'
                }`}
              >
                {(metrics?.benchmark_return || 0) >= 0 ? '+' : ''}
                {(metrics?.benchmark_return || 0).toFixed(2)}%
              </div>
              <span className="text-[10px] text-emerald-600 font-semibold">
                超额 Alpha: {(metrics?.excess_return || 0) >= 0 ? '+' : ''}
                {(metrics?.excess_return || 0).toFixed(2)}%
              </span>
            </div>

            <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                <Zap className="w-3.5 h-3.5 text-indigo-500" />
                年化复合增长率
              </span>
              <div
                className={`text-base font-extrabold mt-1 ${
                  (metrics?.annual_return || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'
                }`}
              >
                {(metrics?.annual_return || 0) >= 0 ? '+' : ''}
                {(metrics?.annual_return || 0).toFixed(2)}%
              </div>
              <span className="text-[10px] text-slate-400">CAGR 真实复利推演</span>
            </div>

            <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-rose-500" />
                最大动态回撤
              </span>
              <div className="text-base font-extrabold text-rose-600 mt-1">
                -{(metrics?.max_drawdown || 0).toFixed(2)}%
              </div>
              <span className="text-[10px] text-slate-400">极值峰谷下挫幅度</span>
            </div>

            <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                <Activity className="w-3.5 h-3.5 text-emerald-500" />
                夏普比率 (Sharpe)
              </span>
              <div className="text-base font-extrabold text-slate-800 mt-1">
                {(metrics?.sharpe_ratio || 0).toFixed(2)}
              </div>
              <span className="text-[10px] text-slate-400">单位波动超额收益</span>
            </div>

            <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                <Award className="w-3.5 h-3.5 text-indigo-500" />
                持仓胜率 / 调仓
              </span>
              <div className="text-base font-extrabold text-slate-800 mt-1">
                {(metrics?.win_rate || 0).toFixed(1)}%
              </div>
              <span className="text-[10px] text-slate-400">
                调仓笔数: {metrics?.rebalance_count || 0} 笔
              </span>
            </div>
          </div>

          {/* Interactive Yield & NAV Curve Chart Section (收益走势与基准对比折线图) */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
              <div>
                <h4 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-indigo-600" />
                  <span>【{curAcc.account_name}】模拟收益走势 vs 中证转债基准</span>
                </h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  双曲线前向跟踪：展示策略组合与中证转债指数(sh000832)的同周期表现与阿尔法超额。
                </p>
              </div>

              <div className="flex items-center flex-wrap gap-2">
                {/* Mode Selector: 收益率 vs 净值 */}
                <div className="inline-flex p-0.5 bg-slate-100 rounded-lg text-xs font-semibold">
                  <button
                    onClick={() => setChartMode('return')}
                    className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                      chartMode === 'return'
                        ? 'bg-white text-indigo-600 shadow-xs'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    累计收益率 (%)
                  </button>
                  <button
                    onClick={() => setChartMode('nav')}
                    className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                      chartMode === 'nav'
                        ? 'bg-white text-indigo-600 shadow-xs'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    绝对净值 (NAV)
                  </button>
                </div>

                {/* Time Range Filter */}
                <div className="inline-flex p-0.5 bg-slate-100 rounded-lg text-xs font-semibold">
                  {(['1W', '1M', '3M', 'ALL'] as const).map((r) => (
                    <button
                      key={r}
                      onClick={() => setTimeRange(r)}
                      className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                        timeRange === r
                          ? 'bg-indigo-600 text-white shadow-xs'
                          : 'text-slate-500 hover:text-slate-800'
                      }`}
                    >
                      {r === '1W' ? '近1周' : r === '1M' ? '近1月' : r === '3M' ? '近3月' : '全部'}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* ECharts Curve Component */}
            {chartData.length > 0 ? (
              <div className="h-[340px] w-full pt-1">
                <ReactECharts
                  option={getChartOption()}
                  style={{ height: '100%', width: '100%' }}
                  notMerge={true}
                  lazyUpdate={true}
                />
              </div>
            ) : (
              <div className="h-[260px] flex flex-col items-center justify-center text-slate-400 text-xs">
                <TrendingUp className="w-10 h-10 text-slate-300 mb-2" />
                <p>该账户暂无足够的历史时序点，点击上方【补齐60天轨迹】或【立即模拟调仓】即可生成丰富走势！</p>
              </div>
            )}
          </div>

          {/* Details Section: Current Positions vs Trade Orders (持仓明细与调仓记录) */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            {/* Tab Header */}
            <div className="px-4 py-2.5 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab('positions')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                    activeTab === 'positions'
                      ? 'bg-white text-indigo-600 shadow-xs'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <Briefcase className="w-3.5 h-3.5" />
                  <span>当前模拟持仓 ({Object.keys(curAcc.positions || {}).length} 只)</span>
                </button>
                <button
                  onClick={() => setActiveTab('trades')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                    activeTab === 'trades'
                      ? 'bg-white text-indigo-600 shadow-xs'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <History className="w-3.5 h-3.5" />
                  <span>模拟调仓流水 ({navDetail?.history_trades?.length || 0} 笔)</span>
                </button>
              </div>

              <div className="text-[11px] text-slate-500">
                可用现金: <b className="text-slate-800">¥{curAcc.available_cash.toLocaleString()}</b>
              </div>
            </div>

            {/* Tab 1: Current Positions Table */}
            {activeTab === 'positions' && (
              <div>
                {Object.keys(curAcc.positions || {}).length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                        <tr>
                          <th className="py-2.5 px-4">转债代码</th>
                          <th className="py-2.5 px-4">转债名称</th>
                          <th className="py-2.5 px-4">买入均价</th>
                          <th className="py-2.5 px-4">当前市价</th>
                          <th className="py-2.5 px-4">持仓张数</th>
                          <th className="py-2.5 px-4">持仓市值 (元)</th>
                          <th className="py-2.5 px-4">浮动盈亏</th>
                          <th className="py-2.5 px-4">仓位占比</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {Object.values(curAcc.positions).map((pos: PositionItem) => {
                          const profitRate = pos.profit_rate || 0;
                          const totalAsset = curAcc.total_asset || curAcc.initial_capital || 100000;
                          const weightPct = totalAsset > 0 ? ((pos.market_value / totalAsset) * 100).toFixed(1) : '0.0';

                          return (
                            <tr key={pos.bond_code} className="hover:bg-slate-50/60 transition-colors">
                              <td className="py-2.5 px-4 font-mono font-bold text-slate-800">
                                {pos.bond_code}
                              </td>
                              <td className="py-2.5 px-4 font-semibold text-slate-900">
                                {pos.bond_name}
                              </td>
                              <td className="py-2.5 px-4 text-slate-600">
                                ¥{pos.avg_price?.toFixed(2)}
                              </td>
                              <td className="py-2.5 px-4 text-slate-900 font-bold">
                                ¥{pos.current_price?.toFixed(2)}
                              </td>
                              <td className="py-2.5 px-4 text-slate-600 font-medium">
                                {pos.amount} 张
                              </td>
                              <td className="py-2.5 px-4 font-bold text-slate-900">
                                ¥{pos.market_value?.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                              </td>
                              <td className="py-2.5 px-4">
                                <span
                                  className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                    profitRate >= 0
                                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                      : 'bg-rose-50 text-rose-700 border border-rose-200'
                                  }`}
                                >
                                  {profitRate >= 0 ? '+' : ''}
                                  {profitRate.toFixed(2)}%
                                </span>
                              </td>
                              <td className="py-2.5 px-4 text-slate-500 font-medium">
                                {weightPct}%
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-8 text-center text-slate-400 text-xs">
                    <Info className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p>该模拟账户当前暂无持仓，点击上方【立即模拟调仓】即可按【{curAcc.associated_strategy}】选券建仓！</p>
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Trade Order History Table */}
            {activeTab === 'trades' && (
              <div>
                {navDetail?.history_trades && navDetail.history_trades.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-100">
                        <tr>
                          <th className="py-2.5 px-4">成交时间</th>
                          <th className="py-2.5 px-4">操作方向</th>
                          <th className="py-2.5 px-4">标的代码</th>
                          <th className="py-2.5 px-4">标的名称</th>
                          <th className="py-2.5 px-4">成交单价</th>
                          <th className="py-2.5 px-4">成交张数</th>
                          <th className="py-2.5 px-4">成交金额</th>
                          <th className="py-2.5 px-4">交易佣金</th>
                          <th className="py-2.5 px-4">策略调仓理由</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-sans">
                        {navDetail.history_trades.map((tr) => (
                          <tr key={tr.order_id} className="hover:bg-slate-50/60 transition-colors">
                            <td className="py-2.5 px-4 font-mono text-slate-500">
                              {tr.trade_time}
                            </td>
                            <td className="py-2.5 px-4">
                              <span
                                className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                                  tr.action === 'BUY'
                                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                    : 'bg-rose-50 text-rose-700 border border-rose-200'
                                }`}
                              >
                                {tr.action === 'BUY' ? '买入建仓' : '卖出轮出'}
                              </span>
                            </td>
                            <td className="py-2.5 px-4 font-mono font-bold text-slate-800">
                              {tr.bond_code}
                            </td>
                            <td className="py-2.5 px-4 font-semibold text-slate-900">
                              {tr.bond_name}
                            </td>
                            <td className="py-2.5 px-4 text-slate-700">
                              ¥{tr.price?.toFixed(2)}
                            </td>
                            <td className="py-2.5 px-4 text-slate-700 font-medium">
                              {tr.amount} 张
                            </td>
                            <td className="py-2.5 px-4 font-bold text-slate-900">
                              ¥{(tr.price * tr.amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="py-2.5 px-4 text-slate-500">
                              ¥{tr.fee?.toFixed(2)}
                            </td>
                            <td className="py-2.5 px-4 text-slate-600 max-w-[260px] truncate" title={tr.reason}>
                              {tr.reason}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-8 text-center text-slate-400 text-xs">
                    <History className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p>暂无模拟调仓记录，点击上方【立即模拟调仓】执行策略轮动。</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal: 新建模拟赛马账户 */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl max-w-md w-full shadow-2xl border border-slate-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <Gamepad2 className="w-4 h-4 text-indigo-600" />
                <h3 className="font-bold text-sm text-slate-900">创建新模拟赛马账户</h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-5 space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 mb-1">模拟盘名称</label>
                <input
                  type="text"
                  required
                  placeholder="例如: 模拟盘 3: AI微盘探索仓"
                  value={newAccName}
                  onChange={(e) => setNewAccName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">绑定的量化策略</label>
                <select
                  value={newAccStrategy}
                  onChange={(e) => setNewAccStrategy(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-hidden bg-white"
                >
                  {strategies.map((s) => (
                    <option key={s.id} value={s.name}>
                      {s.name} ({s.category})
                    </option>
                  ))}
                  {strategies.length === 0 && (
                    <>
                      <option value="经典双低轮动">经典双低轮动</option>
                      <option value="高YTM防守反击">高YTM防守反击</option>
                      <option value="小盘高弹性进取">小盘高弹性进取</option>
                      <option value="AI多智能体增强型">AI多智能体增强型</option>
                    </>
                  )}
                </select>
                <p className="text-[10px] text-slate-400 mt-1">
                  账户每日调仓将严格按照所选策略的筛选指标与打分权重执行。
                </p>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">初始虚拟资金 (元)</label>
                <input
                  type="number"
                  required
                  min={10000}
                  step={10000}
                  value={newAccCapital}
                  onChange={(e) => setNewAccCapital(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="auto_seed_check"
                  checked={newAccAutoSeed}
                  onChange={(e) => setNewAccAutoSeed(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 cursor-pointer"
                />
                <label htmlFor="auto_seed_check" className="font-medium text-slate-700 cursor-pointer">
                  自动预演补齐近 60 个交易日真实历史轨迹 (推荐)
                </label>
              </div>

              <div className="pt-2 flex justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg transition-colors cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition-all shadow-sm cursor-pointer"
                >
                  {actionLoading ? '正在创建...' : '立即开立并加入赛马'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
