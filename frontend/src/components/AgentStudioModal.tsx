import React, { useState, useEffect } from 'react';
import { AgentDefinition } from '../types';
import { api } from '../api/client';
import {
  X,
  Bot,
  Plus,
  Trash2,
  Edit3,
  CheckCircle2,
  AlertCircle,
  Save,
  Cpu,
  Layers,
  Sparkles,
  Sliders,
  Shield,
  Zap,
  Scale
} from 'lucide-react';

interface AgentStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAgentsChanged?: () => void;
}

export const AgentStudioModal: React.FC<AgentStudioModalProps> = ({
  isOpen,
  onClose,
  onAgentsChanged,
}) => {
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Partial<AgentDefinition> | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const data = await api.getAgentTalentPool();
      if (Array.isArray(data)) setAgents(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchAgents();
      setEditingAgent(null);
      setMsg(null);
    }
  }, [isOpen]);

  const handleEdit = (agent: AgentDefinition) => {
    setEditingAgent({ ...agent });
  };

  const handleCreateNew = () => {
    setEditingAgent({
      name: '宏观与行业景气度研究员',
      avatar: '🔭',
      target_asset: 'universal',
      role_type: 'score',
      description: '分析所属产业链中观景气度、库存周期反转与下游需求拉动',
      model_provider: 'auto',
      model_name: '',
      system_prompt: '你是一名顶级买方机构的【行业景气度分析师】。你的职责是从中观产业生命周期、供需库存剪刀差与政策扶持力度审视标的成长确定性。',
      user_prompt_template: '标的: {bond_name} ({bond_code}), 正股: {stock_name}。请分析其所处行业目前处于成长期还是出清期，给出 0-100 景气度评分与核心逻辑。',
      is_builtin: false,
      is_active: true,
      sort_order: 10,
    });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAgent || !editingAgent.name) return;

    setSaveLoading(true);
    try {
      await api.saveCustomAgent(editingAgent);
      setMsg(`已成功保存智能体【${editingAgent.name}】！`);
      setTimeout(() => setMsg(null), 3000);
      setEditingAgent(null);
      fetchAgents();
      if (onAgentsChanged) onAgentsChanged();
    } catch (err: any) {
      alert(`保存失败: ${err.message}`);
    } finally {
      setSaveLoading(false);
    }
  };

  const handleDelete = async (agentId: string, name: string) => {
    if (!window.confirm(`确定要注销并删除智能体【${name}】吗？`)) return;

    try {
      await api.deleteCustomAgent(agentId);
      setMsg(`已删除智能体【${name}】`);
      setTimeout(() => setMsg(null), 2500);
      fetchAgents();
      if (onAgentsChanged) onAgentsChanged();
    } catch (err: any) {
      alert(`删除失败: ${err.message}`);
    }
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'veto':
        return <span className="bg-rose-100 text-rose-800 text-[10px] px-2 py-0.5 rounded font-semibold border border-rose-200">一票否决权 (Veto)</span>;
      case 'prosecutor':
        return <span className="bg-rose-100 text-rose-800 text-[10px] px-2 py-0.5 rounded font-semibold border border-rose-200">做空公诉人 (Prosecutor)</span>;
      case 'defender':
        return <span className="bg-emerald-100 text-emerald-800 text-[10px] px-2 py-0.5 rounded font-semibold border border-emerald-200">多头辩护人 (Defender)</span>;
      case 'judge':
        return <span className="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded font-semibold border border-amber-200">首席大法官 (Judge)</span>;
      case 'score':
        return <span className="bg-blue-100 text-blue-800 text-[10px] px-2 py-0.5 rounded font-semibold border border-blue-200">弹性评分 (Score)</span>;
      default:
        return <span className="bg-purple-100 text-purple-800 text-[10px] px-2 py-0.5 rounded font-semibold border border-purple-200">条款研判 (Review)</span>;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-linear-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center shadow-xs">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-slate-900 flex items-center gap-2">
                <span>投研智能体工坊 (Agent Studio)</span>
                <span className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded-full font-semibold">
                  多空法庭 & 投委会人才库
                </span>
              </h3>
              <p className="text-xs text-slate-500">
                按需定制属于您自己的 AI 分析师、做空公诉人与多头律师，设定专属投资人设与 Prompt
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Notification message */}
        {msg && (
          <div className="px-6 py-2 bg-emerald-50 border-b border-emerald-100 text-emerald-700 text-xs font-semibold flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>{msg}</span>
          </div>
        )}

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Action Bar */}
          <div className="flex justify-between items-center">
            <div className="text-xs text-slate-600">
              当前人才库席位共 <b className="text-slate-900">{agents.length}</b> 位 (包含系统经典席位与用户自创席位)
            </div>
            <button
              onClick={handleCreateNew}
              className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-xs transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>雇佣/新增自定义智能体</span>
            </button>
          </div>

          {/* Edit Form Modal Drawer */}
          {editingAgent && (
            <div className="bg-indigo-50/40 rounded-xl border border-indigo-200 p-5 space-y-4 animate-in fade-in">
              <div className="flex justify-between items-center border-b border-indigo-100 pb-2">
                <span className="font-bold text-xs text-indigo-900 flex items-center gap-1.5">
                  <Edit3 className="w-4 h-4 text-indigo-600" />
                  <span>{editingAgent.id ? `调校智能体配置 · ${editingAgent.name}` : '雇佣全新智能体角色'}</span>
                </span>
                <button
                  type="button"
                  onClick={() => setEditingAgent(null)}
                  className="text-xs text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  取消
                </button>
              </div>

              <form onSubmit={handleSave} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      头像 / Emoji
                    </label>
                    <input
                      type="text"
                      value={editingAgent.avatar || '🤖'}
                      onChange={(e) => setEditingAgent({ ...editingAgent, avatar: e.target.value })}
                      className="w-full text-xs bg-white border border-slate-200 rounded-lg px-3 py-1.5 font-semibold text-slate-800 focus:outline-hidden"
                      maxLength={4}
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      智能体名称
                    </label>
                    <input
                      type="text"
                      required
                      value={editingAgent.name || ''}
                      onChange={(e) => setEditingAgent({ ...editingAgent, name: e.target.value })}
                      className="w-full text-xs bg-white border border-slate-200 rounded-lg px-3 py-1.5 font-semibold text-slate-800 focus:outline-hidden"
                      placeholder="例如：纯债底防守分析师"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      职责权限类型
                    </label>
                    <select
                      value={editingAgent.role_type || 'score'}
                      onChange={(e) => setEditingAgent({ ...editingAgent, role_type: e.target.value })}
                      className="w-full text-xs bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 font-semibold text-slate-800 focus:outline-hidden"
                    >
                      <option value="score">📈 弹性打分型 (Score 0-100)</option>
                      <option value="veto">🚫 极度风控一票否决型 (Veto)</option>
                      <option value="review">♟️ 条款推演型 (Review)</option>
                      <option value="prosecutor">🔴 法庭空方做空公诉人 (Prosecutor)</option>
                      <option value="defender">🟢 法庭多方价值辩护人 (Defender)</option>
                      <option value="judge">⚖️ 法庭主审大法官 (Judge)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      适配资产分类
                    </label>
                    <select
                      value={editingAgent.target_asset || 'universal'}
                      onChange={(e) => setEditingAgent({ ...editingAgent, target_asset: e.target.value })}
                      className="w-full text-xs bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 font-semibold text-slate-800 focus:outline-hidden"
                    >
                      <option value="cb">🏛️ 可转债 (CB)</option>
                      <option value="stock">📈 A股个股 (Stock)</option>
                      <option value="us_stock">🇺🇸 美股标的 (US Stock)</option>
                      <option value="universal">🌐 通用跨资产 (Universal)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                      首选算力渠道
                    </label>
                    <select
                      value={editingAgent.model_provider || 'auto'}
                      onChange={(e) => setEditingAgent({ ...editingAgent, model_provider: e.target.value })}
                      className="w-full text-xs bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 font-semibold text-slate-800 focus:outline-hidden"
                    >
                      <option value="auto">🤖 跟随全局激活模型</option>
                      <option value="gemini">Google Gemini</option>
                      <option value="deepseek">DeepSeek 深度求索</option>
                      <option value="qwen">通义千问 (Qwen)</option>
                      <option value="openai">OpenAI / 兼容接口</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    职责简述与投资哲学
                  </label>
                  <input
                    type="text"
                    value={editingAgent.description || ''}
                    onChange={(e) => setEditingAgent({ ...editingAgent, description: e.target.value })}
                    className="w-full text-xs bg-white border border-slate-200 rounded-lg px-3 py-1.5 font-medium text-slate-800 focus:outline-hidden"
                    placeholder="简述该智能体在投委会或法庭中扮演的核心角色"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    人设与推演准则 (System Prompt)
                  </label>
                  <textarea
                    rows={3}
                    value={editingAgent.system_prompt || ''}
                    onChange={(e) => setEditingAgent({ ...editingAgent, system_prompt: e.target.value })}
                    className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2.5 font-mono text-slate-800 focus:outline-hidden leading-relaxed"
                    placeholder="定义专家的视角、性格以及必须关注的指标与防守底线..."
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                    标的审查提示词模板 (User Prompt Template)
                  </label>
                  <textarea
                    rows={2}
                    value={editingAgent.user_prompt_template || ''}
                    onChange={(e) => setEditingAgent({ ...editingAgent, user_prompt_template: e.target.value })}
                    className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2.5 font-mono text-slate-800 focus:outline-hidden leading-relaxed"
                    placeholder="支持变量: {bond_name}, {bond_code}, {stock_name}, {price}, {premium_rate}, {rating} 等"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setEditingAgent(null)}
                    className="px-4 py-1.5 text-xs text-slate-600 hover:text-slate-800 font-semibold cursor-pointer"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={saveLoading}
                    className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-5 py-2 rounded-xl shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                  >
                    <Save className="w-4 h-4" />
                    <span>{saveLoading ? '保存中...' : '确认保存入库'}</span>
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Agents Grid List */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="bg-white p-4 rounded-xl border border-slate-200 hover:border-indigo-300 transition-all shadow-2xs hover:shadow-xs space-y-2.5 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xl shrink-0">{agent.avatar || '🤖'}</span>
                      <div>
                        <div className="font-bold text-xs text-slate-900 flex items-center gap-1.5">
                          <span>{agent.name}</span>
                          {agent.is_builtin && (
                            <span className="bg-slate-100 text-slate-600 text-[9px] px-1.5 py-0.2 rounded font-medium">
                              内置席位
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div>{getRoleBadge(agent.role_type)}</div>
                  </div>

                  <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                    {agent.description || agent.system_prompt}
                  </p>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <Cpu className="w-3 h-3 text-slate-400" />
                    <span>渠道: {agent.model_provider === 'auto' ? '跟随全局' : agent.model_provider}</span>
                  </span>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleEdit(agent)}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold px-2 py-1 rounded hover:bg-indigo-50 transition-colors cursor-pointer"
                    >
                      编辑
                    </button>
                    {!agent.is_builtin && (
                      <button
                        onClick={() => handleDelete(agent.id, agent.name)}
                        className="text-xs text-rose-500 hover:text-rose-700 font-semibold p-1 rounded hover:bg-rose-50 transition-colors cursor-pointer"
                        title="删除智能体"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 text-xs font-semibold bg-slate-200 hover:bg-slate-300 text-slate-800 rounded-xl transition-colors cursor-pointer"
          >
            完成并关闭
          </button>
        </div>
      </div>
    </div>
  );
};
