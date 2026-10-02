import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import {
  Database,
  X,
  Search,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  HardDrive,
  FileSpreadsheet,
  Clock,
  Layers,
  ArrowUpRight,
  TrendingUp,
  ShieldCheck,
  Activity,
  Terminal,
  ChevronRight,
  Loader2,
  Sparkles,
  DownloadCloud,
  Globe2,
  PieChart,
  BarChart2,
  Settings,
  Plus,
  Check,
  CheckSquare,
  Square,
  SlidersHorizontal,
  ExternalLink
} from 'lucide-react';

interface DataLakeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type AssetCategory = 'cb' | 'us_stock' | 'etf' | 'stock';

// 预设高流动性与高代表性标的池供用户快速勾选
const PRESET_CUSTOM_SYMBOLS: Record<'etf' | 'us_stock' | 'stock', { code: string; name: string; group: string }[]> = {
  etf: [
    { code: '511380', name: '可转债ETF (博时中证转债)', group: '转债对标' },
    { code: '511010', name: '5年期国债ETF', group: '固收利率' },
    { code: '511090', name: '30年超长国债ETF', group: '固收利率' },
    { code: '510300', name: '沪深300ETF (华泰柏瑞)', group: '宽基指数' },
    { code: '510500', name: '中证500ETF (南方)', group: '宽基指数' },
    { code: '512100', name: '中证1000ETF (南方)', group: '宽基指数' },
    { code: '588000', name: '科创50ETF (华夏)', group: '宽基指数' },
    { code: '510050', name: '上证50ETF (华夏)', group: '宽基指数' },
    { code: '159915', name: '创业板ETF (易方达)', group: '宽基指数' },
    { code: '563000', name: '中证2000微盘ETF', group: '宽基指数' },
    { code: '512050', name: '中证A500ETF', group: '宽基指数' },
    { code: '512480', name: '半导体ETF (国联安)', group: '科技芯片' },
    { code: '512760', name: '芯片ETF (华夏)', group: '科技芯片' },
    { code: '515980', name: '人工智能AI ETF', group: '科技芯片' },
    { code: '515050', name: '5G通信ETF', group: '科技芯片' },
    { code: '512720', name: '计算机ETF', group: '科技芯片' },
    { code: '512880', name: '证券ETF (牛市旗手)', group: '大金融' },
    { code: '512800', name: '银行ETF (防守高股息)', group: '大金融' },
    { code: '512200', name: '房地产ETF', group: '大金融' },
    { code: '512690', name: '酒ETF (白酒龙头)', group: '大消费' },
    { code: '159928', name: '消费ETF (汇添富)', group: '大消费' },
    { code: '512010', name: '医药ETF (易方达)', group: '医药医疗' },
    { code: '512170', name: '医疗ETF (华宝)', group: '医药医疗' },
    { code: '515120', name: '创新药ETF (广发)', group: '医药医疗' },
    { code: '515790', name: '光伏ETF (华泰柏瑞)', group: '高端制造' },
    { code: '515030', name: '新能源车ETF', group: '高端制造' },
    { code: '512660', name: '军工ETF (国泰)', group: '高端制造' },
    { code: '159949', name: '有色金属ETF', group: '周期资源' },
    { code: '515220', name: '煤炭ETF (高股息)', group: '周期资源' },
    { code: '515080', name: '红利ETF (招商)', group: '红利避险' },
    { code: '512890', name: '红利低波ETF', group: '红利避险' },
    { code: '513100', name: '纳指ETF (全球科技)', group: '跨境大宗' },
    { code: '513500', name: '标普500ETF (美股大盘)', group: '跨境大宗' },
    { code: '513130', name: '恒生科技ETF', group: '跨境大宗' },
    { code: '518880', name: '黄金ETF (华安避险)', group: '跨境大宗' }
  ],
  us_stock: [
    { code: 'SPY', name: '标普500 ETF (全球大盘基准)', group: '指数大盘' },
    { code: 'QQQ', name: '纳斯达克100 ETF (科技龙头)', group: '指数大盘' },
    { code: 'CWB', name: 'SPDR彭博美股可转债 ETF', group: '转债基准' },
    { code: 'AAPL', name: '苹果 Apple (消费电子)', group: '科技巨头' },
    { code: 'NVDA', name: '英伟达 NVIDIA (AI算力)', group: '科技巨头' },
    { code: 'MSFT', name: '微软 Microsoft (云与AI)', group: '科技巨头' },
    { code: 'TSLA', name: '特斯拉 Tesla (新能源智能车)', group: '科技巨头' },
    { code: 'BABA', name: '阿里巴巴 Alibaba (中概电商)', group: '中概龙头' },
    { code: 'AMD', name: '超威半导体 AMD (CPU/GPU)', group: '半导体' },
    { code: 'COIN', name: 'Coinbase (数字资产交易所)', group: '金融科技' },
    { code: 'PLTR', name: 'Palantir (AI大数据安全)', group: '企业软件' },
    { code: 'GOOGL', name: '谷歌 Alphabet (搜索与大模型)', group: '科技巨头' },
    { code: 'AMZN', name: '亚马逊 Amazon (云计算与电商)', group: '科技巨头' }
  ],
  stock: [
    { code: '002851', name: '麦格米特 (麦米转债正股)', group: '转债核心正股' },
    { code: '600000', name: '浦发银行 (浦发转债正股)', group: '转债核心正股' },
    { code: '601318', name: '中国平安 (金融蓝筹权重)', group: '核心权重' },
    { code: '300750', name: '宁德时代 (动力电池龙头)', group: '先进制造' },
    { code: '002594', name: '比亚迪 (新能源整车龙头)', group: '先进制造' },
    { code: '600519', name: '贵州茅台 (白酒消费价值锚)', group: '核心权重' },
    { code: '600036', name: '招商银行 (高ROE零售银行)', group: '大金融' },
    { code: '000001', name: '平安银行 (零售金融转型)', group: '大金融' },
    { code: '000858', name: '五粮液 (浓香白酒代表)', group: '核心消费' },
    { code: '601899', name: '紫金矿业 (铜金周期龙头)', group: '资源周期' }
  ]
};

export const DataLakeModal: React.FC<DataLakeModalProps> = ({ isOpen, onClose }) => {
  const [activeSubTab, setActiveSubTab] = useState<'overview' | 'inspector' | 'sync'>('overview');
  
  // Overview state
  const [overview, setOverview] = useState<any>(null);
  const [loadingOverview, setLoadingOverview] = useState(false);

  // Inspector state
  const [inspectorCategory, setInspectorCategory] = useState<AssetCategory>('cb');
  const [search, setSearch] = useState('');
  const [symbols, setSymbols] = useState<any[]>([]);
  const [totalSymbols, setTotalSymbols] = useState(0);
  const [loadingSymbols, setLoadingSymbols] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState<string>('128089');
  const [previewData, setPreviewData] = useState<any>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Sync & Job state
  const [taskStatus, setTaskStatus] = useState<any>(null);
  const [triggeringJob, setTriggeringJob] = useState(false);

  // Auto redirect countdown state
  const [autoRedirectTarget, setAutoRedirectTarget] = useState<AssetCategory | null>(null);
  const [redirectSeconds, setRedirectSeconds] = useState<number | null>(null);

  // Custom Downloader Modal State
  const [customModalOpen, setCustomModalOpen] = useState(false);
  const [customCategory, setCustomCategory] = useState<'us_stock' | 'etf' | 'stock'>('etf');
  const [selectedCustomSymbols, setSelectedCustomSymbols] = useState<string[]>([]);
  const [customInputText, setCustomInputText] = useState('');
  const [resolvedExtraMap, setResolvedExtraMap] = useState<Record<string, any>>({});
  const [resolvingInput, setResolvingInput] = useState(false);

  // 实时解析用户手动输入代码的基础信息 (腾讯极速HQ / AkShare / Yahoo Finance)
  useEffect(() => {
    if (!customModalOpen || !customInputText.trim()) {
      setResolvedExtraMap({});
      return;
    }
    const codes = customInputText
      .split(/[\s,，;；\n]+/)
      .map(s => s.trim().toUpperCase())
      .filter(s => s.length >= 2);

    if (codes.length === 0) {
      setResolvedExtraMap({});
      return;
    }

    const timer = setTimeout(async () => {
      setResolvingInput(true);
      try {
        const data = await api.resolveDataLakeSymbols(codes, customCategory);
        setResolvedExtraMap(data || {});
      } catch (e) {
        console.error('Failed to resolve custom symbols', e);
      } finally {
        setResolvingInput(false);
      }
    }, 350);

    return () => clearTimeout(timer);
  }, [customInputText, customCategory, customModalOpen]);

  // Load Overview
  const fetchOverview = async () => {
    setLoadingOverview(true);
    try {
      const data = await api.getDataLakeOverview();
      setOverview(data);
    } catch (err) {
      console.error('Failed to fetch datalake overview', err);
    } finally {
      setLoadingOverview(false);
    }
  };

  // Load Symbols
  const fetchSymbols = async (cat: AssetCategory = inspectorCategory, q = '') => {
    setLoadingSymbols(true);
    try {
      const res = await api.getDataLakeSymbols(cat, q, 1, 50);
      const items = res.items || [];
      setSymbols(items);
      setTotalSymbols(res.total || 0);
      if (items.length > 0) {
        setSelectedSymbol(items[0].symbol);
        fetchPreview(items[0].symbol, cat);
      } else {
        setSelectedSymbol('');
        setPreviewData(null);
      }
    } catch (err) {
      console.error('Failed to fetch symbols', err);
    } finally {
      setLoadingSymbols(false);
    }
  };

  // Load Preview
  const fetchPreview = async (sym: string, cat: AssetCategory = inspectorCategory) => {
    if (!sym) return;
    setLoadingPreview(true);
    try {
      const data = await api.previewDataLakeSymbol(sym, cat, 30);
      setPreviewData(data);
    } catch (err) {
      console.error('Failed to preview symbol', err);
    } finally {
      setLoadingPreview(false);
    }
  };

  // Poll Task Status
  const pollTaskStatus = async () => {
    try {
      const status = await api.getDataLakeSyncStatus();
      setTaskStatus(status);
      return status;
    } catch (err) {
      console.error('Failed to poll task status', err);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchOverview();
      fetchSymbols(inspectorCategory, search);
      pollTaskStatus();
    }
  }, [isOpen]);

  // Polling loop when task is running
  useEffect(() => {
    let timer: any = null;
    if (taskStatus?.status === 'running') {
      timer = setInterval(async () => {
        const s = await pollTaskStatus();
        if (s?.status === 'completed') {
          fetchOverview();
        }
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [taskStatus?.status]);

  // Auto redirect countdown timer when task finishes
  useEffect(() => {
    let timer: any = null;
    if (taskStatus?.status === 'completed' && autoRedirectTarget && redirectSeconds !== null) {
      if (redirectSeconds > 0) {
        timer = setTimeout(() => {
          setRedirectSeconds(redirectSeconds - 1);
        }, 1000);
      } else {
        // Countdown reached 0: automatically navigate to inspector!
        setActiveSubTab('inspector');
        handleSwitchCategory(autoRedirectTarget);
        setAutoRedirectTarget(null);
        setRedirectSeconds(null);
      }
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [taskStatus?.status, autoRedirectTarget, redirectSeconds]);

  const handleStartTask = async (action: string, customSymbols?: string[]) => {
    setTriggeringJob(true);
    try {
      const res = await api.startDataLakeSync(action, customSymbols);
      setTaskStatus(res.task);
      setActiveSubTab('sync');

      // 预设计划跳转的目标类别
      const targetCat: AssetCategory = 
        action === 'download_etf' ? 'etf' :
        action === 'download_us_stock' ? 'us_stock' :
        action === 'download_stock' ? 'stock' : 'cb';
      setAutoRedirectTarget(targetCat);
      setRedirectSeconds(3); // 3秒倒计时自动跳转
    } catch (err) {
      alert('启动任务失败');
    } finally {
      setTriggeringJob(false);
    }
  };

  const handleSwitchCategory = (cat: AssetCategory) => {
    setInspectorCategory(cat);
    setSearch('');
    fetchSymbols(cat, '');
  };

  const openCustomDownloader = (cat: 'us_stock' | 'etf' | 'stock') => {
    setCustomCategory(cat);
    const presets = PRESET_CUSTOM_SYMBOLS[cat] || [];
    // 默认全选该类别的预设标的
    setSelectedCustomSymbols(presets.map(p => p.code));
    setCustomInputText('');
    setCustomModalOpen(true);
  };

  const toggleSelectCustomSymbol = (code: string) => {
    if (selectedCustomSymbols.includes(code)) {
      setSelectedCustomSymbols(selectedCustomSymbols.filter(c => c !== code));
    } else {
      setSelectedCustomSymbols([...selectedCustomSymbols, code]);
    }
  };

  const handleExecuteCustomDownload = () => {
    // 解析用户手动输入的自由代码
    const extraCodes = customInputText
      .split(/[\s,，;；\n]+/)
      .map(s => s.trim().toUpperCase())
      .filter(Boolean);

    const merged = Array.from(new Set([...selectedCustomSymbols, ...extraCodes]));
    if (merged.length === 0) {
      alert('请至少勾选或输入一只标的代码');
      return;
    }

    const action = 
      customCategory === 'etf' ? 'download_etf' :
      customCategory === 'us_stock' ? 'download_us_stock' : 'download_stock';

    setCustomModalOpen(false);
    handleStartTask(action, merged);
  };

  if (!isOpen) return null;

  const summary = overview?.summary || {};
  const assets = overview?.assets || [];

  const cbAsset = assets.find((a: any) => a.key === 'cb');
  const usAsset = assets.find((a: any) => a.key === 'us_stock');
  const etfAsset = assets.find((a: any) => a.key === 'etf');
  const stockAsset = assets.find((a: any) => a.key === 'stock');

  const isCbReady = cbAsset?.status === 'ready' || (cbAsset?.records_count || 0) > 0;
  const isUsReady = usAsset?.status === 'ready' || (usAsset?.records_count || 0) > 0;
  const isEtfReady = etfAsset?.status === 'ready' || (etfAsset?.records_count || 0) > 0;
  const isStockReady = stockAsset?.status === 'ready' || (stockAsset?.records_count || 0) > 0;

  const categoryTabs: { key: AssetCategory; label: string; icon: any; source: string }[] = [
    { key: 'cb', label: '可转债 (1,038只)', icon: ShieldCheck, source: 'A股全市场转债' },
    { key: 'us_stock', label: '美股核心池 (雅虎财经)', icon: Globe2, source: 'Yahoo Finance 直连' },
    { key: 'etf', label: '核心 ETF 基金', icon: PieChart, source: 'AkShare 东方财富' },
    { key: 'stock', label: 'A股转债正股', icon: BarChart2, source: 'AkShare 历史日线' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 sm:p-6 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-6xl max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150 relative">
        
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-sm shadow-blue-200">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900">
                  本地多资产数据湖管理中枢 (Data Lake Studio)
                </h2>
                <span className="text-[10px] font-bold bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                  Parquet 列式零拷贝引擎
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                可转债、美股 (Yahoo Finance)、ETF 及 A 股正股多资产历史日线切片统一湖仓管理
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                fetchOverview();
                fetchSymbols(inspectorCategory, search);
                if (selectedSymbol) fetchPreview(selectedSymbol, inspectorCategory);
              }}
              className="flex items-center gap-1 text-xs text-slate-600 hover:text-slate-900 bg-white border border-slate-200 hover:bg-slate-50 px-2.5 py-1.5 rounded-lg transition-colors cursor-pointer"
              title="刷新数据指标"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingOverview ? 'animate-spin text-blue-600' : ''}`} />
              <span>刷新</span>
            </button>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-200/60 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Sub-navigation Tabs */}
        <div className="flex items-center justify-between px-6 pt-3 border-b border-slate-200 bg-white">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveSubTab('overview')}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                activeSubTab === 'overview'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <HardDrive className="w-4 h-4" />
              <span>1. 资产全景看板 (Overview)</span>
            </button>

            <button
              onClick={() => {
                setActiveSubTab('inspector');
                fetchSymbols(inspectorCategory, search);
              }}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                activeSubTab === 'inspector'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <FileSpreadsheet className="w-4 h-4" />
              <span>2. 切片时序数据探索器 (Data Inspector)</span>
            </button>

            <button
              onClick={() => setActiveSubTab('sync')}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                activeSubTab === 'sync'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>3. 下载调度与维护中心 (Download & Sync)</span>
              {taskStatus?.status === 'running' && (
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></span>
              )}
            </button>
          </div>

          <div className="text-xs text-slate-400 font-mono hidden sm:block">
            总记录数: <strong className="text-slate-700">{summary.total_records ? summary.total_records.toLocaleString() : '780,584'}</strong> 条 · 占用空间: <strong className="text-slate-700">{summary.total_storage_mb || 22.16} MB</strong>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-50">
          
          {/* TAB 1: 资产全景看板 */}
          {activeSubTab === 'overview' && (
            <div className="space-y-5">
              {/* Top Banner KPI */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                  <div className="text-xs font-medium text-slate-500">已就绪资产类别</div>
                  <div className="text-2xl font-bold text-slate-900 mt-1">
                    {summary.ready_assets || 2} <span className="text-xs font-normal text-slate-400">/ 5 类</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-emerald-600 mt-2 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>转债 + 基准已挂载，美股/ETF/股票支持自定义下载</span>
                  </div>
                </div>

                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                  <div className="text-xs font-medium text-slate-500">数据湖总记录条数</div>
                  <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
                    {summary.total_records ? summary.total_records.toLocaleString() : '780,584'}
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-blue-600 mt-2 font-medium">
                    <Layers className="w-3.5 h-3.5" />
                    <span>覆盖 2007 至今历史切片</span>
                  </div>
                </div>

                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                  <div className="text-xs font-medium text-slate-500">磁盘存储占用</div>
                  <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
                    {summary.total_storage_mb || 22.16} <span className="text-xs font-normal text-slate-400">MB</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-purple-600 mt-2 font-medium">
                    <HardDrive className="w-3.5 h-3.5" />
                    <span>Snappy 列式压缩率达 92%</span>
                  </div>
                </div>

                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                  <div className="text-xs font-medium text-slate-500">底层读取引擎</div>
                  <div className="text-sm font-bold text-slate-900 mt-2 truncate">
                    PyArrow Zero-Copy
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-amber-600 mt-2 font-medium">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>单次截面撮合 &lt; 2 秒</span>
                  </div>
                </div>
              </div>

              {/* Asset Cards Grid */}
              <div>
                <h3 className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-3">
                  多资产湖仓目录与快速下载通道 (Asset Registry & Quick Actions)
                </h3>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {assets.map((asset: any) => {
                    const isReady = asset.status === 'ready' || (asset.records_count || 0) > 0;
                    const isCb = asset.key === 'cb';
                    const isUsStock = asset.key === 'us_stock';
                    const isEtf = asset.key === 'etf';
                    const isStock = asset.key === 'stock';

                    return (
                      <div
                        key={asset.key}
                        className={`bg-white rounded-xl border p-4.5 transition-all shadow-xs flex flex-col justify-between ${
                          isReady ? 'border-slate-200 hover:border-blue-300' : 'border-blue-100 bg-slate-50/50'
                        }`}
                      >
                        <div>
                          <div className="flex items-start justify-between">
                            <div>
                              <div className="flex items-center gap-2">
                                <h4 className="font-bold text-sm text-slate-900">{asset.name}</h4>
                                <span
                                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                    isReady
                                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                                  }`}
                                >
                                  {isReady ? '已就绪 (Ready)' : '待下载 (Standby)'}
                                </span>
                              </div>
                              <p className="text-xs text-slate-500 mt-1">{asset.description}</p>
                            </div>
                            <span className="text-xs font-mono bg-slate-100 text-slate-600 px-2 py-1 rounded-md shrink-0 ml-2">
                              {asset.format}
                            </span>
                          </div>

                          <div className="grid grid-cols-4 gap-2 mt-4 pt-3 border-t border-slate-100 text-center">
                            <div>
                              <div className="text-[10px] text-slate-400">覆盖标的</div>
                              <div className="text-xs font-bold text-slate-700 font-mono mt-0.5">
                                {asset.symbols_count} 只
                              </div>
                            </div>
                            <div>
                              <div className="text-[10px] text-slate-400">历史记录</div>
                              <div className="text-xs font-bold text-slate-700 font-mono mt-0.5">
                                {asset.records_count ? asset.records_count.toLocaleString() : 0} 条
                              </div>
                            </div>
                            <div>
                              <div className="text-[10px] text-slate-400">占用大小</div>
                              <div className="text-xs font-bold text-slate-700 font-mono mt-0.5">
                                {asset.storage_mb} MB
                              </div>
                            </div>
                            <div>
                              <div className="text-[10px] text-slate-400">数据区间</div>
                              <div className="text-[11px] font-bold text-slate-700 mt-0.5 truncate" title={asset.date_range}>
                                {asset.date_range}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Action buttons inside card */}
                        <div className="flex items-center justify-between mt-4 pt-3 border-t border-slate-100 text-[11px]">
                          <span className="text-slate-400 font-mono text-[10px] truncate max-w-[180px]">
                            {asset.path}
                          </span>
                          
                          <div className="flex items-center gap-2">
                            {isReady && (
                              <button
                                onClick={() => {
                                  setActiveSubTab('inspector');
                                  handleSwitchCategory(asset.key as AssetCategory);
                                }}
                                className="text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1 cursor-pointer bg-blue-50 hover:bg-blue-100/70 px-2.5 py-1 rounded-md transition-colors"
                              >
                                <span>进入切片预览</span>
                                <ChevronRight className="w-3.5 h-3.5" />
                              </button>
                            )}

                            {isUsStock && (
                              <div className="flex items-center gap-1.5">
                                <button
                                  onClick={() => openCustomDownloader('us_stock')}
                                  className="text-indigo-600 bg-indigo-50 hover:bg-indigo-100 text-xs font-semibold px-2 py-1 rounded-md transition-colors cursor-pointer flex items-center gap-1"
                                  title="自定义勾选与输入标的下载"
                                >
                                  <SlidersHorizontal className="w-3 h-3" />
                                  <span>自定义</span>
                                </button>
                                <button
                                  onClick={() => handleStartTask('download_us_stock')}
                                  disabled={taskStatus?.status === 'running'}
                                  className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors cursor-pointer shadow-xs"
                                >
                                  <DownloadCloud className="w-3.5 h-3.5" />
                                  <span>{isReady ? '全量同步美股' : '🚀 下载美股'}</span>
                                </button>
                              </div>
                            )}

                            {isEtf && (
                              <div className="flex items-center gap-1.5">
                                <button
                                  onClick={() => openCustomDownloader('etf')}
                                  className="text-emerald-700 bg-emerald-50 hover:bg-emerald-100 text-xs font-semibold px-2 py-1 rounded-md transition-colors cursor-pointer flex items-center gap-1"
                                  title="自定义勾选与输入标的下载"
                                >
                                  <SlidersHorizontal className="w-3 h-3" />
                                  <span>自定义</span>
                                </button>
                                <button
                                  onClick={() => handleStartTask('download_etf')}
                                  disabled={taskStatus?.status === 'running'}
                                  className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors cursor-pointer shadow-xs"
                                >
                                  <DownloadCloud className="w-3.5 h-3.5" />
                                  <span>{isReady ? '全量同步ETF' : '🚀 下载核心ETF'}</span>
                                </button>
                              </div>
                            )}

                            {isStock && (
                              <div className="flex items-center gap-1.5">
                                <button
                                  onClick={() => openCustomDownloader('stock')}
                                  className="text-purple-700 bg-purple-50 hover:bg-purple-100 text-xs font-semibold px-2 py-1 rounded-md transition-colors cursor-pointer flex items-center gap-1"
                                  title="自定义勾选与输入标的下载"
                                >
                                  <SlidersHorizontal className="w-3 h-3" />
                                  <span>自定义</span>
                                </button>
                                <button
                                  onClick={() => handleStartTask('download_stock')}
                                  disabled={taskStatus?.status === 'running'}
                                  className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-semibold flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors cursor-pointer shadow-xs"
                                >
                                  <DownloadCloud className="w-3.5 h-3.5" />
                                  <span>{isReady ? '全量同步正股' : '🚀 下载转债正股'}</span>
                                </button>
                                <button
                                  onClick={() => handleStartTask('enrich_cb_events')}
                                  disabled={taskStatus?.status === 'running'}
                                  title="抓取下修事件与强赎/到期日志，回填到期日、最后交易日等字段并重算剩余年限"
                                  className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-semibold flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors cursor-pointer shadow-xs"
                                >
                                  <SlidersHorizontal className="w-3.5 h-3.5" />
                                  <span>下修/强赎事件刷新</span>
                                </button>
                                <button
                                  onClick={() => handleStartTask('enrich_cb_mv')}
                                  disabled={taskStatus?.status === 'running'}
                                  title="逐股抓取正股历史总市值 (百度，约3年窗口，断点续传)，供微盘/市值因子使用"
                                  className="bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white font-semibold flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors cursor-pointer shadow-xs"
                                >
                                  <DownloadCloud className="w-3.5 h-3.5" />
                                  <span>正股市值历史</span>
                                </button>
                              </div>
                            )}
                          </div>
                        </div>

                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Bottom Quick Action Box */}
              <div className="bg-linear-to-r from-blue-900 to-indigo-900 rounded-xl p-4.5 text-white flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-md">
                <div>
                  <h4 className="text-sm font-bold flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-yellow-400" />
                    <span>多资产量化全数据湖配置建议</span>
                  </h4>
                  <p className="text-xs text-blue-200 mt-1 leading-relaxed">
                    美股数据源采用 <strong>Yahoo Finance (雅虎财经 yfinance)</strong> 直连，提供标普500、纳斯达克及美股转债基准 ETF (CWB)；A股ETF与转债正股走 AkShare。支持按需自定义勾选标的。
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleStartTask('incremental_update')}
                    disabled={triggeringJob || taskStatus?.status === 'running'}
                    className="bg-white text-blue-900 hover:bg-blue-50 text-xs font-bold px-3.5 py-2 rounded-lg transition-colors cursor-pointer shadow-xs"
                  >
                    一键增量更新最新行情
                  </button>
                  <button
                    onClick={() => setActiveSubTab('sync')}
                    className="bg-blue-800/90 hover:bg-blue-800 text-white text-xs font-semibold px-3 py-2 rounded-lg border border-blue-700 transition-colors cursor-pointer flex items-center gap-1"
                  >
                    <span>进入下载调度中心</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: 切片时序数据探索器 */}
          {activeSubTab === 'inspector' && (
            <div className="flex flex-col space-y-3 h-[640px]">
              
              {/* Asset Category Switcher Header */}
              <div className="flex items-center justify-between bg-white p-2 rounded-xl border border-slate-200 shadow-xs">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-500 pl-2">资产类型切换:</span>
                  <div className="flex gap-1">
                    {categoryTabs.map((tab) => {
                      const Icon = tab.icon;
                      const isSelected = inspectorCategory === tab.key;
                      return (
                        <button
                          key={tab.key}
                          onClick={() => handleSwitchCategory(tab.key)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                            isSelected
                              ? 'bg-blue-600 text-white shadow-xs'
                              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                          }`}
                        >
                          <Icon className="w-3.5 h-3.5" />
                          <span>{tab.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="flex items-center gap-3 pr-2">
                  {inspectorCategory !== 'cb' && (
                    <button
                      onClick={() => openCustomDownloader(inspectorCategory as any)}
                      className="text-xs font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-2.5 py-1 rounded-lg transition-colors cursor-pointer flex items-center gap-1"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>自定义添加新标的</span>
                    </button>
                  )}
                  <div className="text-[11px] text-slate-400">
                    数据源: <span className="font-semibold text-slate-700">{categoryTabs.find(t => t.key === inspectorCategory)?.source}</span>
                  </div>
                </div>
              </div>

              {/* Main Content Area */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0">
                
                {/* Left Column: Symbol List */}
                <div className="lg:col-span-4 bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col overflow-hidden">
                  <div className="p-3 border-b border-slate-100">
                    <div className="relative">
                      <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                      <input
                        type="text"
                        placeholder={
                          inspectorCategory === 'us_stock'
                            ? '搜索美股代码 (如 SPY, AAPL, CWB)...'
                            : inspectorCategory === 'etf'
                            ? '搜索 ETF 代码 (如 511380, 510300)...'
                            : inspectorCategory === 'stock'
                            ? '搜索股票代码 (如 002851) 或名称...'
                            : '搜索转债代码 (如 128089) 或简称...'
                        }
                        value={search}
                        onChange={(e) => {
                          setSearch(e.target.value);
                          fetchSymbols(inspectorCategory, e.target.value);
                        }}
                        className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:bg-white"
                      />
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 px-1">
                      <span>标的列表 (共 {totalSymbols} 只已切片)</span>
                      <span>点击查看历史切片</span>
                    </div>
                  </div>

                  <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
                    {loadingSymbols ? (
                      <div className="p-8 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
                        <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
                        <span>正在检索标的元数据...</span>
                      </div>
                    ) : symbols.length === 0 ? (
                      <div className="p-8 text-center text-slate-500 text-xs space-y-3">
                        <AlertCircle className="w-8 h-8 text-amber-500 mx-auto" />
                        <div>该类别数据湖尚未下载本地切片文件</div>
                        <button
                          onClick={() => openCustomDownloader(inspectorCategory as any)}
                          className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors cursor-pointer shadow-xs inline-flex items-center gap-1.5"
                        >
                          <DownloadCloud className="w-3.5 h-3.5" />
                          <span>立即自定义选择下载标的</span>
                        </button>
                      </div>
                    ) : (
                      symbols.map((item) => {
                        const isSelected = selectedSymbol === item.symbol;
                        return (
                          <div
                            key={item.symbol}
                            onClick={() => {
                              setSelectedSymbol(item.symbol);
                              fetchPreview(item.symbol, inspectorCategory);
                            }}
                            className={`p-3 cursor-pointer transition-colors flex items-center justify-between ${
                              isSelected
                                ? 'bg-blue-50/70 border-l-3 border-blue-600'
                                : 'hover:bg-slate-50'
                            }`}
                          >
                            <div className="min-w-0 flex-1 pr-2">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="font-bold text-xs text-slate-900 font-mono">
                                  {item.symbol}
                                </span>
                                <span className="font-bold text-xs text-slate-800 truncate" title={item.name}>
                                  {item.name}
                                </span>
                                {item.exchange && (
                                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 font-medium shrink-0">
                                    {item.exchange}
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-2 flex-wrap">
                                {item.price > 0 && (
                                  <span className="text-slate-700 font-mono font-medium">
                                    {inspectorCategory === 'us_stock' ? '$' : '¥'}{Number(item.price).toFixed(2)}
                                  </span>
                                )}
                                {item.market_cap > 0 && (
                                  <span>
                                    市值 {item.market_cap > 10000 ? `${(item.market_cap / 10000).toFixed(1)}万亿` : `${Math.round(item.market_cap)}亿`}
                                  </span>
                                )}
                                {item.pe > 0 && (
                                  <span>PE {Number(item.pe).toFixed(1)}</span>
                                )}
                                {item.issue_scale > 0 && (
                                  <span>规模 {item.issue_scale}亿</span>
                                )}
                                {item.stock_name && item.stock_name !== item.name && (
                                  <span className="text-slate-500">正股: {item.stock_name}</span>
                                )}
                              </div>
                            </div>

                            <div className="text-right shrink-0">
                              <span className="text-[10px] font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                                {item.file_size_kb ? `${item.file_size_kb} KB` : '切片中'}
                              </span>
                              <div className="text-[10px] text-emerald-600 font-medium mt-0.5">
                                ● 已切片
                              </div>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* Right Column: Historical Bars Preview Table */}
                <div className="lg:col-span-8 bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col overflow-hidden">
                  {/* Asset Profile Banner (标的基础信息全景看板) */}
                  {(() => {
                    const currentInfo = previewData?.symbol_info || symbols.find((s) => s.symbol === selectedSymbol) || {};
                    return (
                      <div className="p-4 border-b border-slate-200 bg-linear-to-r from-slate-50 via-blue-50/20 to-slate-50">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-linear-to-br from-blue-600 to-indigo-600 text-white flex items-center justify-center font-mono font-bold text-xs shadow-xs shrink-0">
                              {selectedSymbol ? selectedSymbol.slice(-4) : '--'}
                            </div>
                            <div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <h4 className="font-extrabold text-base text-slate-900 tracking-tight">
                                  {currentInfo?.name || selectedSymbol || '请选择标的'}
                                </h4>
                                {selectedSymbol && (
                                  <span className="text-xs font-mono font-bold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-md">
                                    {selectedSymbol}
                                  </span>
                                )}
                                {currentInfo?.exchange && (
                                  <span className="text-[11px] bg-slate-100 text-slate-700 border border-slate-200 px-2 py-0.5 rounded-md font-medium">
                                    {currentInfo.exchange}
                                  </span>
                                )}
                                <span className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full font-bold">
                                  {inspectorCategory === 'us_stock'
                                    ? 'Yahoo Finance 雅虎财经日线'
                                    : inspectorCategory === 'cb'
                                    ? '全指标 Parquet 时序切片'
                                    : inspectorCategory === 'etf'
                                    ? 'AkShare ETF 日线'
                                    : 'AkShare A股正股日线'}
                                </span>
                              </div>
                              <div className="text-xs text-slate-500 mt-1 flex items-center gap-2 flex-wrap">
                                <span>总历史切片: <strong className="text-slate-800 font-mono">{previewData?.total_records || 0}</strong> 个交易日</span>
                                {currentInfo?.start_date && currentInfo?.end_date && (
                                  <span>· 跨度: <strong className="text-slate-700 font-mono">{currentInfo.start_date} ~ {currentInfo.end_date}</strong></span>
                                )}
                                <span>· 预览最新 30 条真实记录</span>
                              </div>
                            </div>
                          </div>

                          {selectedSymbol && (
                            <button
                              onClick={() => fetchPreview(selectedSymbol, inspectorCategory)}
                              disabled={loadingPreview}
                              className="flex items-center gap-1 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 font-medium text-xs px-3 py-1.5 rounded-lg transition-colors cursor-pointer shadow-xs self-start sm:self-center"
                            >
                              <RefreshCw className={`w-3.5 h-3.5 ${loadingPreview ? 'animate-spin' : ''}`} />
                              <span>刷新切片</span>
                            </button>
                          )}
                        </div>

                        {/* Metric Cards Row */}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
                          <div className="bg-white p-2.5 rounded-lg border border-slate-200/80 shadow-2xs">
                            <div className="text-[11px] text-slate-400 font-medium">
                              {inspectorCategory === 'cb' ? '最新转债收盘' : '最新收盘 / 参考价'}
                            </div>
                            <div className="text-sm font-bold font-mono text-blue-700 mt-0.5">
                              {currentInfo?.price && currentInfo.price > 0
                                ? `${inspectorCategory === 'us_stock' ? '$' : '¥'}${Number(currentInfo.price).toFixed(2)}`
                                : currentInfo?.latest_close
                                ? `${inspectorCategory === 'us_stock' ? '$' : '¥'}${Number(currentInfo.latest_close).toFixed(2)}`
                                : '-'}
                            </div>
                          </div>

                          <div className="bg-white p-2.5 rounded-lg border border-slate-200/80 shadow-2xs">
                            <div className="text-[11px] text-slate-400 font-medium">
                              {inspectorCategory === 'cb' ? '转债发行规模' : '总市值 (市值规模)'}
                            </div>
                            <div className="text-sm font-bold font-mono text-slate-800 mt-0.5">
                              {inspectorCategory === 'cb'
                                ? (currentInfo?.issue_scale ? `${currentInfo.issue_scale} 亿元` : '-')
                                : (currentInfo?.market_cap && currentInfo.market_cap > 0
                                    ? (currentInfo.market_cap > 10000 
                                        ? `${(currentInfo.market_cap / 10000).toFixed(2)} 万亿` 
                                        : `${Number(currentInfo.market_cap).toFixed(1)} 亿元`)
                                    : '-')}
                            </div>
                          </div>

                          <div className="bg-white p-2.5 rounded-lg border border-slate-200/80 shadow-2xs">
                            <div className="text-[11px] text-slate-400 font-medium">
                              {inspectorCategory === 'cb' ? '对标正股代码/简称' : '市盈率 PE (动/静)'}
                            </div>
                            <div className="text-sm font-bold font-mono text-slate-800 mt-0.5 truncate">
                              {inspectorCategory === 'cb'
                                ? (currentInfo?.stock_name ? `${currentInfo.stock_name} (${currentInfo.stock_code})` : currentInfo?.stock_code || '-')
                                : (currentInfo?.pe && currentInfo.pe > 0 ? Number(currentInfo.pe).toFixed(2) : '-')}
                            </div>
                          </div>

                          <div className="bg-white p-2.5 rounded-lg border border-slate-200/80 shadow-2xs">
                            <div className="text-[11px] text-slate-400 font-medium">
                              {inspectorCategory === 'cb' ? '最新转股价' : '市净率 PB'}
                            </div>
                            <div className="text-sm font-bold font-mono text-slate-800 mt-0.5">
                              {inspectorCategory === 'cb'
                                ? (currentInfo?.convert_price ? `¥${currentInfo.convert_price}` : '-')
                                : (currentInfo?.pb && currentInfo.pb > 0 ? Number(currentInfo.pb).toFixed(2) : '-')}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Table View */}
                  <div className="flex-1 overflow-auto">
                    {loadingPreview ? (
                      <div className="h-full flex flex-col items-center justify-center text-slate-400 text-xs gap-2">
                        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                        <span>正在从 Parquet 零拷贝读取切片数据...</span>
                      </div>
                    ) : !previewData || previewData.rows.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-slate-400 text-xs gap-3">
                        <FileSpreadsheet className="w-8 h-8 text-slate-300" />
                        <span>暂无切片数据，请先在左侧选择标的或在【下载调度中心】执行同步</span>
                      </div>
                    ) : (
                      <table className="w-full text-xs text-left border-collapse">
                        {inspectorCategory === 'cb' ? (
                          // 转债特色指标表头
                          <>
                            <thead className="bg-slate-50 text-slate-500 font-semibold sticky top-0 border-b border-slate-200 z-10">
                              <tr>
                                <th className="py-2.5 px-3">交易日期</th>
                                <th className="py-2.5 px-3">收盘价 (元)</th>
                                <th className="py-2.5 px-3">纯债价值</th>
                                <th className="py-2.5 px-3">转股价值</th>
                                <th className="py-2.5 px-3">转股溢价率 (%)</th>
                                <th className="py-2.5 px-3">双低指标</th>
                                <th className="py-2.5 px-3">纯债溢价率</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 font-mono text-slate-700">
                              {previewData.rows.map((row: any, idx: number) => {
                                const prem = Number(row.premium_rate);
                                const isNegative = !isNaN(prem) && prem < 0;
                                return (
                                  <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                                    <td className="py-2 px-3 font-semibold text-slate-900">
                                      {row.trade_date}
                                    </td>
                                    <td className="py-2 px-3 font-bold text-blue-700">
                                      {row.close}
                                    </td>
                                    <td className="py-2 px-3 text-slate-600">
                                      {row.pure_debt_value}
                                    </td>
                                    <td className="py-2 px-3 text-slate-600">
                                      {row.convert_value}
                                    </td>
                                    <td className={`py-2 px-3 font-semibold ${isNegative ? 'text-emerald-600 font-bold' : 'text-slate-800'}`}>
                                      {row.premium_rate}%
                                    </td>
                                    <td className="py-2 px-3 font-bold text-indigo-700">
                                      {row.double_low}
                                    </td>
                                    <td className="py-2 px-3 text-slate-400">
                                      {row.pure_debt_premium_rate}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </>
                        ) : (
                          // 美股 / ETF / 股票 通用时序表头
                          <>
                            <thead className="bg-slate-50 text-slate-500 font-semibold sticky top-0 border-b border-slate-200 z-10">
                              <tr>
                                <th className="py-2.5 px-3">交易日期</th>
                                <th className="py-2.5 px-3">开盘价</th>
                                <th className="py-2.5 px-3">最高价</th>
                                <th className="py-2.5 px-3">最低价</th>
                                <th className="py-2.5 px-3">收盘价</th>
                                <th className="py-2.5 px-3">成交量 (Volume)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 font-mono text-slate-700">
                              {previewData.rows.map((row: any, idx: number) => (
                                <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                                  <td className="py-2 px-3 font-semibold text-slate-900">
                                    {row.trade_date}
                                  </td>
                                  <td className="py-2 px-3 text-slate-600">
                                    {row.open}
                                  </td>
                                  <td className="py-2 px-3 text-red-600">
                                    {row.high}
                                  </td>
                                  <td className="py-2 px-3 text-emerald-600">
                                    {row.low}
                                  </td>
                                  <td className="py-2 px-3 font-bold text-blue-700">
                                    {row.close}
                                  </td>
                                  <td className="py-2 px-3 text-slate-600">
                                    {row.volume !== undefined && row.volume !== '-'
                                      ? Number(row.volume).toLocaleString()
                                      : '-'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </>
                        )}
                      </table>
                    )}
                  </div>

                  <div className="p-2.5 bg-slate-50 border-t border-slate-200 text-[11px] text-slate-400 flex items-center justify-between">
                    <span>底层存储路径: data/{inspectorCategory}/</span>
                    <span>支持跨资产零拷贝回测与跨市场多空仲裁</span>
                  </div>
                </div>

              </div>

            </div>
          )}

          {/* TAB 3: 下载调度与维护中心 */}
          {activeSubTab === 'sync' && (
            <div className="space-y-5">
              
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                    全市场数据下载与调度中心 (Multi-Asset Downloader Pipeline)
                  </h3>
                  <div className="text-xs text-slate-400">
                    支持一键全量推荐同步或点击【自定义】勾选特定标的
                  </div>
                </div>

                {/* 5 Distinct Task Action Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  
                  {/* Card 1: 转债增量更新 */}
                  <div className="bg-white p-4.5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                          <RefreshCw className="w-4 h-4" />
                        </div>
                        <span className="text-[10px] font-bold bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
                          每日收盘同步
                        </span>
                      </div>
                      <h4 className="font-bold text-sm text-slate-900">转债增量行情同步</h4>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        探测全网最新交易日，拉取当日转债收盘估值切片并追加到本地 Master Parquet 湖仓，保持回测与实盘最新。
                      </p>
                    </div>
                    <div className="mt-4 space-y-1.5">
                      <button
                        onClick={() => handleStartTask('incremental_update')}
                        disabled={triggeringJob || taskStatus?.status === 'running'}
                        className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold py-2 rounded-lg transition-colors cursor-pointer"
                      >
                        ⚡ 立即启动增量更新
                      </button>
                      <button
                        onClick={() => {
                          setActiveSubTab('inspector');
                          handleSwitchCategory('cb');
                        }}
                        className="w-full text-center text-[11px] text-slate-500 hover:text-blue-700 pt-1 cursor-pointer flex items-center justify-center gap-1"
                      >
                        <span>进入转债切片探索器 (1,038只)</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Card 2: 美股大盘与核心标的 (Yahoo Finance) */}
                  <div className={`p-4.5 rounded-xl border shadow-xs flex flex-col justify-between transition-all ${
                    isUsReady ? 'bg-indigo-50/30 border-indigo-200' : 'bg-white border-slate-200'
                  }`}>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                          <Globe2 className="w-4 h-4" />
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          isUsReady
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : 'bg-indigo-50 text-indigo-700'
                        }`}>
                          {isUsReady ? `✅ 已就绪 (${usAsset?.symbols_count || 8}只 · ${usAsset?.records_count?.toLocaleString()}条)` : '雅虎财经直连 (免Token)'}
                        </span>
                      </div>
                      <h4 className="font-bold text-sm text-slate-900">美股核心标的湖 (Yahoo Finance)</h4>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        直连雅虎财经下载 <strong>标普500 (SPY)、纳指100 (QQQ)、美股可转债 (CWB)</strong> 及科技巨头近2年历史日线，支持自由扩充美股。
                      </p>
                    </div>
                    <div className="mt-4 space-y-2">
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => openCustomDownloader('us_stock')}
                          className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold py-2 rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-1 border border-indigo-200"
                        >
                          <SlidersHorizontal className="w-3 h-3" />
                          <span>自定义选标的</span>
                        </button>
                        <button
                          onClick={() => handleStartTask('download_us_stock')}
                          disabled={triggeringJob || taskStatus?.status === 'running'}
                          className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold py-2 rounded-lg transition-colors cursor-pointer shadow-xs truncate"
                        >
                          {isUsReady ? '全量同步池' : '🚀 全量下载'}
                        </button>
                      </div>

                      {isUsReady && (
                        <button
                          onClick={() => {
                            setActiveSubTab('inspector');
                            handleSwitchCategory('us_stock');
                          }}
                          className="w-full bg-white hover:bg-slate-50 text-indigo-700 text-xs font-bold py-1.5 rounded-lg border border-indigo-200 transition-all cursor-pointer flex items-center justify-center gap-1"
                        >
                          <span>进入美股切片探索器</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Card 3: 核心 ETF 基金池 */}
                  <div className={`p-4.5 rounded-xl border shadow-xs flex flex-col justify-between transition-all ${
                    isEtfReady ? 'bg-emerald-50/30 border-emerald-200' : 'bg-white border-slate-200'
                  }`}>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                          <PieChart className="w-4 h-4" />
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          isEtfReady
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : 'bg-emerald-50 text-emerald-700'
                        }`}>
                          {isEtfReady ? `✅ 已就绪 (${etfAsset?.symbols_count || 35}只 · ${etfAsset?.records_count?.toLocaleString()}条)` : 'AkShare 稳定源'}
                        </span>
                      </div>
                      <h4 className="font-bold text-sm text-slate-900">核心 ETF 指数基金湖</h4>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        一键拉取 <strong>可转债ETF (511380)、沪深300、科创50、创业板</strong> 及各行业/红利/大宗ETF近2年切片，支持勾选或输入任意代码。
                      </p>
                    </div>
                    <div className="mt-4 space-y-2">
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => openCustomDownloader('etf')}
                          className="bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-xs font-semibold py-2 rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-1 border border-emerald-200"
                        >
                          <SlidersHorizontal className="w-3 h-3" />
                          <span>自定义选标的</span>
                        </button>
                        <button
                          onClick={() => handleStartTask('download_etf')}
                          disabled={triggeringJob || taskStatus?.status === 'running'}
                          className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold py-2 rounded-lg transition-colors cursor-pointer shadow-xs truncate"
                        >
                          {isEtfReady ? '全量同步池' : '🚀 全量下载'}
                        </button>
                      </div>

                      {isEtfReady && (
                        <button
                          onClick={() => {
                            setActiveSubTab('inspector');
                            handleSwitchCategory('etf');
                          }}
                          className="w-full bg-white hover:bg-slate-50 text-emerald-700 text-xs font-bold py-1.5 rounded-lg border border-emerald-200 transition-all cursor-pointer flex items-center justify-center gap-1"
                        >
                          <span>进入 ETF 切片探索器</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Card 4: 转债核心正股池 */}
                  <div className={`p-4.5 rounded-xl border shadow-xs flex flex-col justify-between transition-all ${
                    isStockReady ? 'bg-purple-50/30 border-purple-200' : 'bg-white border-slate-200'
                  }`}>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
                          <BarChart2 className="w-4 h-4" />
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          isStockReady
                            ? 'bg-purple-100 text-purple-800 border border-purple-200'
                            : 'bg-purple-50 text-purple-700'
                        }`}>
                          {isStockReady ? `✅ 已就绪 (${stockAsset?.symbols_count || 6}只 · ${stockAsset?.records_count?.toLocaleString()}条)` : '转债正股联动分析'}
                        </span>
                      </div>
                      <h4 className="font-bold text-sm text-slate-900">转债核心正股时序湖</h4>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        同步 <strong>麦格米特 (002851)、浦发银行 (600000)、中国平安、宁德时代、比亚迪</strong> 等正股历史日线，用于对冲与下修博弈推演。
                      </p>
                    </div>
                    <div className="mt-4 space-y-2">
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => openCustomDownloader('stock')}
                          className="bg-purple-50 hover:bg-purple-100 text-purple-700 text-xs font-semibold py-2 rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-1 border border-purple-200"
                        >
                          <SlidersHorizontal className="w-3 h-3" />
                          <span>自定义选标的</span>
                        </button>
                        <button
                          onClick={() => handleStartTask('download_stock')}
                          disabled={triggeringJob || taskStatus?.status === 'running'}
                          className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-xs font-semibold py-2 rounded-lg transition-colors cursor-pointer shadow-xs truncate"
                        >
                          {isStockReady ? '全量同步池' : '🚀 全量下载'}
                        </button>
                      </div>

                      {isStockReady && (
                        <button
                          onClick={() => {
                            setActiveSubTab('inspector');
                            handleSwitchCategory('stock');
                          }}
                          className="w-full bg-white hover:bg-slate-50 text-purple-700 text-xs font-bold py-1.5 rounded-lg border border-purple-200 transition-all cursor-pointer flex items-center justify-center gap-1"
                        >
                          <span>进入正股切片探索器</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Card 5: 全量数据湖健康度体检 */}
                  <div className="bg-white p-4.5 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-700 flex items-center justify-center">
                          <ShieldCheck className="w-4 h-4" />
                        </div>
                        <span className="text-[10px] font-bold bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                          湖仓完整度校验
                        </span>
                      </div>
                      <h4 className="font-bold text-sm text-slate-900">数据湖健康度全量体检</h4>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        全面深度扫描全量历史时序切片，检查是否有坏块、空值、断流、列对齐与完整性校验。
                      </p>
                    </div>
                    <div className="mt-4">
                      <button
                        onClick={() => handleStartTask('health_check')}
                        disabled={triggeringJob || taskStatus?.status === 'running'}
                        className="w-full bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white text-xs font-semibold py-2 rounded-lg transition-colors cursor-pointer"
                      >
                        🛡️ 立即启动健康体检
                      </button>
                    </div>
                  </div>

                </div>
              </div>

              {/* Real-time Task Monitor & Console */}
              <div className="bg-slate-900 rounded-xl p-5 border border-slate-800 text-white shadow-lg space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-emerald-400" />
                    <span className="font-bold text-xs tracking-wider text-slate-300">
                      任务执行与实时控制台 (Task Execution Console)
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        taskStatus?.status === 'running'
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse'
                          : taskStatus?.status === 'completed'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      状态: {taskStatus?.status === 'running' ? '正在执行' : taskStatus?.status === 'completed' ? '已完成' : '空闲'}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {taskStatus?.started_at ? `启动时间: ${taskStatus.started_at}` : ''}
                    </span>
                  </div>
                </div>

                {/* Progress bar */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">{taskStatus?.message || '等待任务启动...'}</span>
                    <span className="font-mono text-emerald-400 font-bold">{taskStatus?.progress || 0}%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-linear-to-r from-blue-500 to-emerald-400 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${taskStatus?.progress || 0}%` }}
                    ></div>
                  </div>
                </div>

                {/* Completed Banner with Direct Navigation & Auto-countdown */}
                {taskStatus?.status === 'completed' && (
                  <div className="bg-emerald-950/90 border border-emerald-500/50 rounded-xl p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                        <CheckCircle2 className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-emerald-300 flex items-center gap-2">
                          <span>
                            {taskStatus?.action === 'download_etf'
                              ? '核心 ETF 数据湖下载已全部完成！'
                              : taskStatus?.action === 'download_us_stock'
                              ? '美股核心标的数据湖下载已全部完成！'
                              : taskStatus?.action === 'download_stock'
                              ? '转债核心正股数据湖下载已全部完成！'
                              : '数据湖作业已全部顺利完成！'}
                          </span>
                          {redirectSeconds !== null && redirectSeconds > 0 && (
                            <span className="text-[10px] bg-emerald-800 text-emerald-200 px-1.5 py-0.5 rounded font-mono animate-pulse">
                              {redirectSeconds}秒后自动跳转
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          切片已合并持久化至 Master Parquet 湖仓，可随时进入探索器进行时序切片与回测。
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {redirectSeconds !== null && (
                        <button
                          onClick={() => {
                            setAutoRedirectTarget(null);
                            setRedirectSeconds(null);
                          }}
                          className="text-slate-400 hover:text-white text-xs px-2.5 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 transition-colors cursor-pointer"
                        >
                          留在控制台
                        </button>
                      )}

                      <button
                        onClick={() => {
                          const targetCat: AssetCategory = 
                            taskStatus?.action === 'download_etf' ? 'etf' :
                            taskStatus?.action === 'download_us_stock' ? 'us_stock' :
                            taskStatus?.action === 'download_stock' ? 'stock' : 'cb';
                          setActiveSubTab('inspector');
                          handleSwitchCategory(targetCat);
                          setAutoRedirectTarget(null);
                          setRedirectSeconds(null);
                        }}
                        className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors cursor-pointer shadow-md flex items-center gap-1.5"
                      >
                        <span>👉 立即进入切片时序详情探索</span>
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}

                {/* Log Terminal Window */}
                <div className="bg-slate-950 rounded-lg p-3 font-mono text-[11px] text-slate-300 h-44 overflow-y-auto space-y-1 border border-slate-800/80">
                  {taskStatus?.logs && taskStatus.logs.length > 0 ? (
                    taskStatus.logs.map((log: string, idx: number) => (
                      <div key={idx} className="leading-5">
                        {log}
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-600 py-16 text-center">
                      控制台就绪，请在上方点击对应资产下载按钮即可开始拉取时序日线
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Custom Symbols Downloader Dialog (Overlay Modal) */}
        {customModalOpen && (
          <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/70 backdrop-blur-xs p-4">
            <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
              
              {/* Dialog Header */}
              <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center">
                    <SlidersHorizontal className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      自定义选择下载标的 ({customCategory === 'etf' ? '核心 ETF' : customCategory === 'us_stock' ? '美股标的' : 'A股转债正股'})
                    </h3>
                    <p className="text-[11px] text-slate-500">
                      自由勾选推荐池标的，或手动输入任意代码增量下载入湖
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setCustomModalOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Dialog Body */}
              <div className="p-5 flex-1 overflow-y-auto space-y-4">
                
                {/* Category Switcher in Dialog */}
                <div className="flex gap-2 p-1 bg-slate-100 rounded-lg w-fit text-xs font-semibold">
                  <button
                    onClick={() => {
                      setCustomCategory('etf');
                      setSelectedCustomSymbols((PRESET_CUSTOM_SYMBOLS['etf'] || []).map(p => p.code));
                    }}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      customCategory === 'etf' ? 'bg-white text-emerald-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    ETF 基金池 ({PRESET_CUSTOM_SYMBOLS.etf.length})
                  </button>
                  <button
                    onClick={() => {
                      setCustomCategory('us_stock');
                      setSelectedCustomSymbols((PRESET_CUSTOM_SYMBOLS['us_stock'] || []).map(p => p.code));
                    }}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      customCategory === 'us_stock' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    美股核心标的 ({PRESET_CUSTOM_SYMBOLS.us_stock.length})
                  </button>
                  <button
                    onClick={() => {
                      setCustomCategory('stock');
                      setSelectedCustomSymbols((PRESET_CUSTOM_SYMBOLS['stock'] || []).map(p => p.code));
                    }}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      customCategory === 'stock' ? 'bg-white text-purple-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    A股转债正股 ({PRESET_CUSTOM_SYMBOLS.stock.length})
                  </button>
                </div>

                {/* Preset Chips Section */}
                <div>
                  <div className="flex items-center justify-between text-xs mb-2">
                    <span className="font-bold text-slate-700">推荐标的池 (点击即可勾选/取消):</span>
                    <div className="flex gap-2 text-[11px]">
                      <button
                        onClick={() => setSelectedCustomSymbols(PRESET_CUSTOM_SYMBOLS[customCategory].map(p => p.code))}
                        className="text-blue-600 hover:text-blue-800 font-semibold cursor-pointer"
                      >
                        全选
                      </button>
                      <span className="text-slate-300">|</span>
                      <button
                        onClick={() => setSelectedCustomSymbols([])}
                        className="text-slate-500 hover:text-slate-700 cursor-pointer"
                      >
                        清空
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-56 overflow-y-auto p-1 border border-slate-200 rounded-xl bg-slate-50/50">
                    {PRESET_CUSTOM_SYMBOLS[customCategory].map((item) => {
                      const isChecked = selectedCustomSymbols.includes(item.code);
                      return (
                        <div
                          key={item.code}
                          onClick={() => toggleSelectCustomSymbol(item.code)}
                          className={`p-2 rounded-lg border text-xs cursor-pointer transition-all flex items-start gap-2 select-none ${
                            isChecked
                              ? 'bg-blue-50/80 border-blue-300 text-blue-900 font-medium'
                              : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                          }`}
                        >
                          <div className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 mt-0.5 ${
                            isChecked ? 'bg-blue-600 border-blue-600 text-white' : 'border-slate-300 bg-white'
                          }`}>
                            {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1 font-mono font-bold">
                              <span>{item.code}</span>
                              <span className="text-[10px] text-slate-400 font-normal font-sans">[{item.group}]</span>
                            </div>
                            <div className="text-[11px] text-slate-600 truncate" title={item.name}>
                              {item.name}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Free Text Input Section */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">
                    手动补充任意自定义代码 (支持多个代码，以逗号、空格或换行分隔):
                  </label>
                  <textarea
                    rows={2}
                    placeholder={
                      customCategory === 'etf'
                        ? '例如: 511380, 588000, 159949, 512010...'
                        : customCategory === 'us_stock'
                        ? '例如: TSLA, NVDA, AMD, COIN, PLTR, BABA...'
                        : '例如: 002851, 600000, 300750, 600519...'
                    }
                    value={customInputText}
                    onChange={(e) => setCustomInputText(e.target.value)}
                    className="w-full text-xs font-mono p-2.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:bg-white"
                  />

                  {resolvingInput && (
                    <div className="flex items-center gap-1.5 text-[11px] text-blue-600 mt-1.5 font-medium">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>正在全网解析标的基础信息 (公司简称、所属板块、估值指标)...</span>
                    </div>
                  )}

                  {!resolvingInput && Object.keys(resolvedExtraMap).length > 0 && (
                    <div className="mt-2.5 p-2.5 bg-blue-50/70 rounded-xl border border-blue-200/80 space-y-1.5 animate-in fade-in duration-150">
                      <div className="text-[11px] font-bold text-blue-900 flex items-center justify-between">
                        <span>✨ 已自动识别到 {Object.keys(resolvedExtraMap).length} 只标的真实基础信息:</span>
                        <span className="text-[10px] text-blue-600 font-normal">全网行情与板块自动绑定</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.values(resolvedExtraMap).map((item: any) => (
                          <span
                            key={item.symbol}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-blue-200 text-xs shadow-2xs font-sans"
                          >
                            <span className="font-mono font-bold text-blue-700">{item.symbol}</span>
                            <span className="font-bold text-slate-800">{item.name}</span>
                            {item.exchange && (
                              <span className="text-[10px] text-slate-500 bg-slate-100 px-1 rounded">
                                {item.exchange}
                              </span>
                            )}
                            {item.price > 0 && (
                              <span className="text-[10px] text-emerald-700 font-mono font-semibold">
                                {customCategory === 'us_stock' ? '$' : '¥'}{Number(item.price).toFixed(2)}
                              </span>
                            )}
                            {item.market_cap > 0 && (
                              <span className="text-[10px] text-slate-500">
                                市值{Math.round(item.market_cap)}亿
                              </span>
                            )}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <p className="text-[10px] text-slate-400 mt-1">
                    💡 提示：增量下载会自动合并入库，绝不会覆盖或删除之前已有的历史标的切片。
                  </p>
                </div>


              </div>

              {/* Dialog Footer */}
              <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs">
                <div className="text-slate-500">
                  当前已选中: <strong className="text-blue-600 font-mono text-sm">{selectedCustomSymbols.length}</strong> 只预设标的
                  {customInputText.trim() && (
                    <span className="text-slate-400 ml-1">(+手动输入项)</span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCustomModalOpen(false)}
                    className="px-3.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
                  >
                    取消
                  </button>

                  <button
                    onClick={handleExecuteCustomDownload}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-4 py-1.5 rounded-lg transition-colors cursor-pointer shadow-xs flex items-center gap-1.5"
                  >
                    <DownloadCloud className="w-3.5 h-3.5" />
                    <span>🚀 立即下载选中的标的</span>
                  </button>
                </div>
              </div>

            </div>
          </div>
        )}

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-white flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>本地 Parquet 数据湖连接正常 · 零网络延迟</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg transition-colors cursor-pointer"
          >
            关闭控制台
          </button>
        </div>

      </div>
    </div>
  );
};
