import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import {
  X,
  Calendar,
  Sliders,
  Shield,
  Zap,
  Bot,
  Key,
  Globe,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ExternalLink,
  Eye,
  EyeOff,
  Sparkles,
  Server,
  Cpu,
  Check
} from 'lucide-react';

interface GlobalSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  startDate: string;
  setStartDate: (d: string) => void;
  endDate: string;
  setEndDate: (d: string) => void;
  rebalanceFreq: number;
  setRebalanceFreq: (f: number) => void;
}

type ProviderKey = 'deepseek' | 'qwen' | 'gemini' | 'openai';

export const GlobalSettingsModal: React.FC<GlobalSettingsModalProps> = ({
  isOpen,
  onClose,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  rebalanceFreq,
  setRebalanceFreq,
}) => {
  const [activeTab, setActiveTab] = useState<'ai' | 'backtest'>('ai');

  // LLM Config state
  const [llmConfig, setLlmConfig] = useState<any>(null);
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<ProviderKey>('deepseek');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);

  // Test & Save states
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    latency_ms?: number;
    message?: string;
    error?: string;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

  // Load LLM configuration when opened
  const fetchLLMConfig = async () => {
    setLoadingConfig(true);
    try {
      const data = await api.getLLMConfig();
      setLlmConfig(data);
      const active = data?.active_provider || 'deepseek';
      setSelectedProvider(active as ProviderKey);
      
      const pInfo = data?.providers?.[active];
      if (pInfo) {
        setBaseUrl(pInfo.base_url || '');
        setModel(pInfo.model || '');
      }
    } catch (err) {
      console.error('Failed to load LLM config', err);
    } finally {
      setLoadingConfig(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchLLMConfig();
      setTestResult(null);
      setSaveSuccessMsg(null);
      setApiKey('');
    }
  }, [isOpen]);

  // When user clicks a different provider card
  const handleSelectProvider = (key: ProviderKey) => {
    setSelectedProvider(key);
    setTestResult(null);
    setSaveSuccessMsg(null);
    setApiKey('');
    const pInfo = llmConfig?.providers?.[key];
    if (pInfo) {
      setBaseUrl(pInfo.base_url || '');
      setModel(pInfo.model || '');
    }
  };

  // Test Connection
  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.testLLMConnection({
        provider: selectedProvider,
        api_key: apiKey,
        base_url: baseUrl,
        model: model,
      });
      setTestResult(res);
    } catch (err: any) {
      setTestResult({
        success: false,
        error: err.message || '网络连接异常，无法发起测试请求',
      });
    } finally {
      setTesting(false);
    }
  };

  // Save Config
  const handleSaveConfig = async () => {
    setSaving(true);
    setSaveSuccessMsg(null);
    try {
      const res = await api.saveLLMConfig({
        provider: selectedProvider,
        api_key: apiKey,
        base_url: baseUrl,
        model: model,
      });
      setLlmConfig(res.config);
      setSaveSuccessMsg(`已成功保存并启用 ${llmConfig?.providers?.[selectedProvider]?.name || selectedProvider}！全平台智能体已即时接通。`);
      setApiKey(''); // Clear entered raw key for security
      setTimeout(() => setSaveSuccessMsg(null), 4000);
    } catch (err: any) {
      alert(`保存失败: ${err.message || '未知错误'}`);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const currentProviderInfo = llmConfig?.providers?.[selectedProvider];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center shadow-xs">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">系统全局控制中心</h3>
              <p className="text-[11px] text-slate-500">配置 AI 大模型供应商、API Token 与回测执行环境</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 bg-slate-100/60 px-6 gap-2 pt-2">
          <button
            onClick={() => setActiveTab('ai')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              activeTab === 'ai'
                ? 'border-blue-600 text-blue-700 bg-white rounded-t-lg shadow-2xs'
                : 'border-transparent text-slate-600 hover:text-slate-900'
            }`}
          >
            <Bot className="w-4 h-4 text-blue-600" />
            <span>AI 大模型与 Token 供应商配置</span>
            {llmConfig?.is_ready && (
              <span className="w-2 h-2 rounded-full bg-emerald-500" title="AI 已就绪"></span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('backtest')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              activeTab === 'backtest'
                ? 'border-blue-600 text-blue-700 bg-white rounded-t-lg shadow-2xs'
                : 'border-transparent text-slate-600 hover:text-slate-900'
            }`}
          >
            <Zap className="w-4 h-4 text-amber-500" />
            <span>回测跨度与市场摩擦规则</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5">

          {/* TAB 1: AI 大模型配置 */}
          {activeTab === 'ai' && (
            <div className="space-y-5">
              
              {/* Status Header Banner */}
              <div className="bg-linear-to-r from-blue-50 via-indigo-50/50 to-slate-50 p-3.5 rounded-xl border border-blue-200/70 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-900 flex items-center gap-2">
                      <span>当前激活供应商:</span>
                      <span className="font-mono text-blue-700 font-bold bg-white px-2 py-0.5 rounded border border-blue-200">
                        {llmConfig?.providers?.[llmConfig?.active_provider]?.name || '未配置'}
                      </span>
                      {llmConfig?.is_ready ? (
                        <span className="text-[10px] text-emerald-700 bg-emerald-100 border border-emerald-300 px-2 py-0.5 rounded-full font-semibold flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>已接通可调用</span>
                        </span>
                      ) : (
                        <span className="text-[10px] text-amber-700 bg-amber-100 border border-amber-300 px-2 py-0.5 rounded-full font-semibold flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" />
                          <span>未配置 Token (智能体使用本地规则)</span>
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      赋能信用排雷、条款博弈推演、正股题材动量及 AI 自动探索可转债新策略。
                    </p>
                  </div>
                </div>
              </div>

              {/* Provider Selection Grid */}
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-2">
                  1. 选择你要连接的 AI 大模型供应商 (Provider):
                </label>
                <div className="grid grid-cols-2 gap-2.5">
                  {(['deepseek', 'qwen', 'gemini', 'openai'] as ProviderKey[]).map((pKey) => {
                    const info = llmConfig?.providers?.[pKey];
                    const isSelected = selectedProvider === pKey;
                    const isConfigured = info?.is_configured;
                    return (
                      <div
                        key={pKey}
                        onClick={() => handleSelectProvider(pKey)}
                        className={`p-3 rounded-xl border text-xs cursor-pointer transition-all flex flex-col justify-between ${
                          isSelected
                            ? 'bg-blue-50/80 border-blue-600 ring-2 ring-blue-500/20 shadow-xs'
                            : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-1.5 font-bold text-slate-900">
                            {pKey === 'deepseek' && <span className="text-blue-600">🇨🇳</span>}
                            {pKey === 'qwen' && <span className="text-orange-500">🇨🇳</span>}
                            {pKey === 'gemini' && <span className="text-indigo-600">🌐</span>}
                            {pKey === 'openai' && <span className="text-emerald-600">⚡</span>}
                            <span>{info?.name?.split(' ')[0] || pKey}</span>
                          </div>

                          {isConfigured && (
                            <span className="text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded font-medium flex items-center gap-0.5">
                              <Check className="w-2.5 h-2.5" />
                              <span>已配Key</span>
                            </span>
                          )}
                        </div>

                        <p className="text-[11px] text-slate-500 line-clamp-1 leading-relaxed">
                          {info?.desc || ''}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Selected Provider Parameter Settings Form */}
              <div className="bg-slate-50/80 p-4 rounded-xl border border-slate-200/90 space-y-3.5">
                <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-blue-600" />
                    <span className="text-xs font-bold text-slate-800">
                      配置【{currentProviderInfo?.name || selectedProvider}】连接参数
                    </span>
                  </div>

                  {currentProviderInfo?.token_url && (
                    <a
                      href={currentProviderInfo.token_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1"
                    >
                      <span>前往官方获取 Token / API Key</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>

                {/* API Key Input */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-slate-700 flex items-center gap-1">
                      <Key className="w-3.5 h-3.5 text-blue-600" />
                      <span>API Key / Token:</span>
                    </label>
                    {currentProviderInfo?.is_configured && (
                      <span className="text-[11px] font-mono text-slate-500">
                        当前已保存: <span className="font-semibold text-slate-700">{currentProviderInfo.masked_key}</span>
                      </span>
                    )}
                  </div>

                  <div className="relative">
                    <input
                      type={showApiKey ? 'text' : 'password'}
                      placeholder={
                        currentProviderInfo?.is_configured
                          ? '已配置。如需更改请输入新的 API Key'
                          : '请输入您的 API Key (如 sk-xxxxxxxx...)'
                      }
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      className="w-full text-xs font-mono bg-white border border-slate-200 rounded-lg pl-3 pr-10 py-2 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-2.5 top-2 text-slate-400 hover:text-slate-600 cursor-pointer"
                    >
                      {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">
                    🔒 Token 仅保存于您本地项目根目录的 <code>.env</code> 文件中，绝不上传至任何第三方服务器。
                  </p>
                </div>

                {/* API Base URL */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-slate-700 flex items-center gap-1">
                      <Globe className="w-3.5 h-3.5 text-blue-600" />
                      <span>API Base URL (接口端点):</span>
                    </label>
                    <span className="text-[10px] text-amber-600 bg-amber-50 border border-amber-200 px-1.5 py-0.2 rounded font-medium">
                      支持中转网关 / 反向代理
                    </span>
                  </div>
                  <input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder={currentProviderInfo?.base_url || 'https://api.openai.com/v1'}
                    className="w-full text-xs font-mono bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                  <p className="text-[10px] text-slate-400 mt-1">
                    💡 若您使用中转代理 (如 OneAPI/NewAPI/聚合网关)，请务必将此处修改为您的网关地址 (如 <code>https://your-gateway.com/v1</code>)，否则请求将直连官方被拦截。
                  </p>
                </div>

                {/* Model Name */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1">
                    <Server className="w-3.5 h-3.5 text-blue-600" />
                    <span>模型名称 (Model Name):</span>
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder="deepseek-chat"
                      className="flex-1 text-xs font-mono bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    />
                    {currentProviderInfo?.preset_models && (
                      <select
                        onChange={(e) => setModel(e.target.value)}
                        value={currentProviderInfo.preset_models.includes(model) ? model : ''}
                        className="text-xs bg-white border border-slate-200 rounded-lg px-2.5 py-2 text-slate-700 cursor-pointer"
                      >
                        <option value="" disabled>快速预设</option>
                        {currentProviderInfo.preset_models.map((m: string) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>

                {/* Test Result Message Box */}
                {testResult && (
                  <div className={`p-3 rounded-lg border text-xs flex items-start gap-2.5 ${
                    testResult.success
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                      : 'bg-rose-50 border-rose-200 text-rose-800'
                  }`}>
                    {testResult.success ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1">
                      <div className="font-bold">
                        {testResult.success ? '连通性测试通过！' : '连通性测试未通过'}
                      </div>
                      <div className="text-[11px] mt-0.5">
                        {testResult.message || testResult.error}
                      </div>
                    </div>
                  </div>
                )}

                {/* Save Success Notice */}
                {saveSuccessMsg && (
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 font-medium flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>{saveSuccessMsg}</span>
                  </div>
                )}

                {/* Action Buttons for AI Tab */}
                <div className="flex items-center justify-between pt-2">
                  <button
                    type="button"
                    onClick={handleTestConnection}
                    disabled={testing}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-100 text-slate-700 text-xs font-semibold rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                  >
                    {testing ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />
                    ) : (
                      <Zap className="w-3.5 h-3.5 text-amber-500" />
                    )}
                    <span>{testing ? '正在测试连接...' : '⚡ 测试连通性'}</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleSaveConfig}
                    disabled={saving}
                    className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors cursor-pointer shadow-xs disabled:opacity-50"
                  >
                    {saving ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Check className="w-3.5 h-3.5" />
                    )}
                    <span>{saving ? '保存中...' : '💾 保存并设为默认供应商'}</span>
                  </button>
                </div>

              </div>

            </div>
          )}

          {/* TAB 2: 回测与市场摩擦配置 */}
          {activeTab === 'backtest' && (
            <div className="space-y-4">
              <p className="text-xs text-slate-500 leading-relaxed">
                设置全局历史策略回测的时间跨度与交易滑点摩擦损耗。策略专属逻辑在各个策略工作台中独立配置。
              </p>

              <div className="space-y-3.5 bg-slate-50/70 p-4 rounded-xl border border-slate-200/80">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-blue-500" /> 历史回测起始日期
                  </label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full text-xs bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-blue-500" /> 历史回测截止日期
                  </label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full text-xs bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-amber-500" /> 回测调仓换仓周期
                  </label>
                  <select
                    value={rebalanceFreq}
                    onChange={(e) => setRebalanceFreq(Number(e.target.value))}
                    className="w-full text-xs bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  >
                    <option value={5}>每 5 个交易日 (每周轮动)</option>
                    <option value={10}>每 10 个交易日 (双周轮动)</option>
                    <option value={20}>每 20 个交易日 (月度轮动)</option>
                  </select>
                </div>
              </div>

              <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200/80 space-y-2 text-xs text-slate-600">
                <div className="font-bold text-slate-800 flex items-center gap-1.5">
                  <Shield className="w-4 h-4 text-emerald-500" />
                  <span>市场交易摩擦与基准规则说明</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span>多资产基准适应:</span>
                  <span className="font-semibold text-slate-800">可转债(000832) / 股票(沪深300) / 美股(标普500)</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span>可转债交易佣金:</span>
                  <span className="font-semibold text-slate-800">万分之 0.5 (T+0 交易，免征印花税)</span>
                </div>
                <div className="flex justify-between py-1">
                  <span>流动性冲击滑点:</span>
                  <span className="font-semibold text-slate-800">0.10% (千分之一)</span>
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-200 flex items-center justify-between bg-slate-50/70">
          <div className="text-[11px] text-slate-400">
            配置持久化保存于系统运行环境 · 即改即生效
          </div>

          <button
            onClick={onClose}
            className="bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors cursor-pointer"
          >
            完成并关闭
          </button>
        </div>

      </div>
    </div>
  );
};
