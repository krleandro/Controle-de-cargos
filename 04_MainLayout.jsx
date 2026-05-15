/**
 * =============================================================================
 * SISTEMA DE GESTÃO DE CARGOS E VAGAS (FOPAG) — Prefeitura de Miracema
 * Arquivo: 04_MainLayout.jsx
 * Framework: React 18 + Tailwind CSS v3
 * Estética: Corporate Minimal — fundo branco, paleta azul cobalto, Inter font
 *
 * Arquitetura de Componentes:
 *   <App>
 *     <Sidebar>          — navegação lateral esquerda, fundo cinza ultra-claro
 *     <MainContent>
 *       <Header>         — barra superior: título, busca, ações globais
 *       <StatsBar>       — 4 cards de KPIs (total previstos, ocupados, saldo, alertas)
 *       <TableToolbar>   — filtros de situação/tipo + botão "Novo Cargo"
 *       <CargosTable>    — tabela principal com saldo computado
 *       <LeiModal>       — modal para registrar lei e aplicar impacto
 * =============================================================================
 */

import React, { useState, useMemo, useCallback } from 'react';

// =============================================================================
// DESIGN SYSTEM — TOKENS DE COR (CSS-in-JS + Tailwind)
// Mapeamento completo da paleta branco / azul conforme especificado.
// Em produção com Tailwind, estes valores entrariam em tailwind.config.js.
// =============================================================================

const TOKENS = {
  // Backgrounds
  bg: {
    page:      '#FFFFFF',          // branco absoluto — fundo da área de conteúdo
    sidebar:   '#F8F9FB',          // cinza ultra-claro — sidebar
    card:      '#FFFFFF',          // branco — cards/KPIs
    hover:     '#EFF4FF',          // azul glacial — hover de linhas e itens
    selected:  '#DBEAFE',          // azul claro — linha selecionada (blue-100)
    input:     '#F8F9FB',          // cinza ultra-claro — inputs
  },

  // Paleta azul (todas as ações interativas)
  blue: {
    primary:   '#2563EB',          // azul cobalto — botões primários (blue-600)
    primaryHover:'#1D4ED8',        // azul marinho — hover de botões (blue-700)
    light:     '#3B82F6',          // azul médio — links, ícones (blue-500)
    xlight:    '#BFDBFE',          // azul pastel — badges "Em vigor" (blue-200)
    xlightBg:  '#EFF6FF',          // azul gelo — chips/tags (blue-50)
    dark:      '#1E3A8A',          // azul escuro — textos sobre fundo azul (blue-900)
    focus:     '#93C5FD',          // anel de foco (blue-300)
  },

  // Status semânticos
  status: {
    successBg:  '#ECFDF5', successText: '#065F46',   // verde — saldo positivo
    warningBg:  '#FFFBEB', warningText: '#92400E',   // âmbar — saldo zero
    dangerBg:   '#FEF2F2', dangerText:  '#991B1B',   // vermelho — saldo negativo
    extinctoBg: '#F3F4F6', extinctoText:'#6B7280',   // cinza — cargo extinto
  },

  // Texto
  text: {
    primary:   '#111827',          // quase preto — títulos (gray-900)
    secondary: '#6B7280',          // cinza médio — labels e subtítulos (gray-500)
    muted:     '#9CA3AF',          // cinza claro — placeholders (gray-400)
    onBlue:    '#FFFFFF',          // branco — texto sobre botões azuis
  },

  // Bordas
  border: {
    default:   '#E5E7EB',          // cinza tênue — divisores e bordas de tabela (gray-200)
    focus:     '#3B82F6',          // azul — bordas de inputs com foco
  },
};

// Estilos base reutilizáveis (Tailwind classes como strings)
const cls = {
  btnPrimary:   'inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg text-white transition-colors duration-150',
  btnSecondary: 'inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg border transition-colors duration-150',
  badge:        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
  input:        'w-full px-3 py-2 text-sm rounded-lg border outline-none transition-colors duration-150',
  th:           'px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide',
  td:           'px-4 py-3.5 text-sm whitespace-nowrap',
};


// =============================================================================
// COMPONENTE: Sidebar
// Navegação lateral — fundo cinza ultra-claro, itens ativos em azul
// =============================================================================

const NAV_ITEMS = [
  { id: 'quadro',    label: 'Quadro de Pessoal', icon: '⊞' },
  { id: 'cargos',    label: 'Gestão de Cargos',  icon: '🗂' },
  { id: 'leis',      label: 'Leis Pertinentes',  icon: '⚖' },
  { id: 'relatorio', label: 'Relatórios',         icon: '📊' },
  { id: 'config',    label: 'Configurações',      icon: '⚙' },
];

function Sidebar({ activeNav, onNavChange }) {
  return (
    <aside style={{ width: 240, minHeight: '100vh', background: TOKENS.bg.sidebar,
                    borderRight: `1px solid ${TOKENS.border.default}`, display: 'flex',
                    flexDirection: 'column', padding: '0' }}>

      {/* Logo / Identidade */}
      <div style={{ padding: '28px 24px 20px', borderBottom: `1px solid ${TOKENS.border.default}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: TOKENS.blue.primary,
                        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ color: '#fff', fontSize: 16 }}>⊞</span>
          </div>
          <div>
            <p style={{ fontSize: 13, fontWeight: 700, color: TOKENS.text.primary, lineHeight: 1.2 }}>FOPAG</p>
            <p style={{ fontSize: 10, color: TOKENS.text.secondary, lineHeight: 1.2 }}>Quadro de Pessoal</p>
          </div>
        </div>
      </div>

      {/* Itens de navegação */}
      <nav style={{ flex: 1, padding: '16px 12px' }}>
        {NAV_ITEMS.map(item => {
          const isActive = activeNav === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavChange(item.id)}
              style={{
                width: '100%', textAlign: 'left', display: 'flex', alignItems: 'center',
                gap: 10, padding: '9px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
                marginBottom: 2, fontSize: 13, fontWeight: isActive ? 600 : 400,
                background: isActive ? TOKENS.bg.selected : 'transparent',
                color: isActive ? TOKENS.blue.primary : TOKENS.text.secondary,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = TOKENS.bg.hover; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
            >
              <span style={{ fontSize: 15 }}>{item.icon}</span>
              {item.label}
              {isActive && (
                <div style={{ marginLeft: 'auto', width: 4, height: 4, borderRadius: '50%',
                              background: TOKENS.blue.primary }} />
              )}
            </button>
          );
        })}
      </nav>

      {/* Rodapé da sidebar */}
      <div style={{ padding: '16px 24px', borderTop: `1px solid ${TOKENS.border.default}` }}>
        <p style={{ fontSize: 10, color: TOKENS.text.muted, lineHeight: 1.5 }}>
          Prefeitura Municipal<br />de Miracema
        </p>
      </div>
    </aside>
  );
}


// =============================================================================
// COMPONENTE: Header
// Barra superior com título, busca global e ação de novo cargo
// =============================================================================

function Header({ searchTerm, onSearch, onNovoCargo }) {
  return (
    <header style={{ padding: '20px 32px', borderBottom: `1px solid ${TOKENS.border.default}`,
                     background: TOKENS.bg.page, display: 'flex', alignItems: 'center',
                     justifyContent: 'space-between', gap: 16 }}>
      {/* Título */}
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: TOKENS.text.primary, margin: 0 }}>
          Quadro de Pessoal
        </h1>
        <p style={{ fontSize: 12, color: TOKENS.text.secondary, margin: '2px 0 0' }}>
          Cargos efetivos e comissionados — Prefeitura de Miracema
        </p>
      </div>

      {/* Busca + Ação */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Campo de busca */}
        <div style={{ position: 'relative' }}>
          <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
                         color: TOKENS.text.muted, fontSize: 14 }}>🔍</span>
          <input
            type="text"
            placeholder="Buscar cargo ou código FOPAG..."
            value={searchTerm}
            onChange={e => onSearch(e.target.value)}
            style={{ ...{}, paddingLeft: 32, paddingRight: 12, paddingTop: 8, paddingBottom: 8,
                     fontSize: 13, width: 280, borderRadius: 8, border: `1px solid ${TOKENS.border.default}`,
                     background: TOKENS.bg.input, color: TOKENS.text.primary, outline: 'none',
                     fontFamily: 'inherit', transition: 'border-color 0.15s' }}
            onFocus={e => e.target.style.borderColor = TOKENS.border.focus}
            onBlur={e => e.target.style.borderColor = TOKENS.border.default}
          />
        </div>

        {/* Botão primário — azul cobalto */}
        <button
          onClick={onNovoCargo}
          style={{ ...{}, display: 'inline-flex', alignItems: 'center', gap: 6,
                   padding: '8px 16px', fontSize: 13, fontWeight: 600, borderRadius: 8,
                   border: 'none', cursor: 'pointer', background: TOKENS.blue.primary,
                   color: TOKENS.text.onBlue, transition: 'background 0.15s ease' }}
          onMouseEnter={e => e.currentTarget.style.background = TOKENS.blue.primaryHover}
          onMouseLeave={e => e.currentTarget.style.background = TOKENS.blue.primary}
        >
          <span style={{ fontSize: 16, lineHeight: 1 }}>+</span>
          Novo Cargo
        </button>
      </div>
    </header>
  );
}


// =============================================================================
// COMPONENTE: StatsBar
// 4 cards de KPI com valores do quadro de pessoal
// =============================================================================

function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{ flex: 1, background: TOKENS.bg.card, border: `1px solid ${TOKENS.border.default}`,
                  borderRadius: 12, padding: '20px 24px', position: 'relative', overflow: 'hidden' }}>
      {/* Linha de destaque colorida no topo */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3,
                    background: accent, borderRadius: '12px 12px 0 0' }} />
      <p style={{ fontSize: 11, fontWeight: 600, color: TOKENS.text.secondary,
                  textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 8px' }}>
        {label}
      </p>
      <p style={{ fontSize: 28, fontWeight: 700, color: TOKENS.text.primary, margin: '0 0 4px',
                  lineHeight: 1 }}>
        {value}
      </p>
      {sub && <p style={{ fontSize: 11, color: TOKENS.text.secondary, margin: 0 }}>{sub}</p>}
    </div>
  );
}

function StatsBar({ dados }) {
  const saldoColor = dados.totalSaldo > 0
    ? TOKENS.status.successText
    : dados.totalSaldo < 0
      ? TOKENS.status.dangerText
      : TOKENS.status.warningText;

  return (
    <div style={{ display: 'flex', gap: 16, padding: '24px 32px 0' }}>
      <StatCard label="Total Previstos"  value={dados.totalPrevistos.toLocaleString('pt-BR')}
                sub="vagas no quadro"   accent={TOKENS.blue.primary} />
      <StatCard label="Total Ocupados"   value={dados.totalOcupados.toLocaleString('pt-BR')}
                sub="vagas providas"    accent={TOKENS.blue.light} />
      <StatCard label="Saldo de Vagas"   value={dados.totalSaldo.toLocaleString('pt-BR')}
                sub="disponíveis"       accent={saldoColor} />
      <StatCard label="Alertas"          value={dados.alertas}
                sub="saldos negativos"  accent={TOKENS.status.dangerText} />
    </div>
  );
}


// =============================================================================
// COMPONENTE: TableToolbar
// Filtros de situação, tipo de provimento e export
// =============================================================================

function TableToolbar({ filtros, onChange, totalFiltrado, onRegistrarLei }) {
  const btnSecStyle = (active) => ({
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px',
    fontSize: 12, fontWeight: active ? 600 : 400, borderRadius: 6, border: 'none',
    cursor: 'pointer', transition: 'all 0.15s',
    background: active ? TOKENS.bg.selected : 'transparent',
    color:      active ? TOKENS.blue.primary : TOKENS.text.secondary,
  });

  return (
    <div style={{ padding: '20px 32px 0', display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>

      {/* Filtros de situação */}
      <div style={{ display: 'flex', gap: 4, background: TOKENS.bg.sidebar,
                    borderRadius: 8, padding: 4, border: `1px solid ${TOKENS.border.default}` }}>
        {['Todos', 'Em vigor', 'Extinto', 'Revogado'].map(s => (
          <button key={s} style={btnSecStyle(filtros.situacao === s)}
                  onClick={() => onChange({ ...filtros, situacao: s })}>
            {s}
          </button>
        ))}
      </div>

      {/* Filtros de tipo */}
      <div style={{ display: 'flex', gap: 4, background: TOKENS.bg.sidebar,
                    borderRadius: 8, padding: 4, border: `1px solid ${TOKENS.border.default}` }}>
        {['Todos', 'Efetivo', 'Comissão'].map(t => (
          <button key={t} style={btnSecStyle(filtros.tipo === t)}
                  onClick={() => onChange({ ...filtros, tipo: t })}>
            {t}
          </button>
        ))}
      </div>

      {/* Contador + ação secundária */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginLeft: 'auto' }}>
        <span style={{ fontSize: 12, color: TOKENS.text.secondary }}>
          {totalFiltrado} cargo{totalFiltrado !== 1 ? 's' : ''} encontrado{totalFiltrado !== 1 ? 's' : ''}
        </span>
        <button
          onClick={onRegistrarLei}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px',
                   fontSize: 12, fontWeight: 600, borderRadius: 8, cursor: 'pointer',
                   border: `1px solid ${TOKENS.blue.primary}`, background: TOKENS.bg.xlightBg,
                   color: TOKENS.blue.primary, transition: 'all 0.15s' }}
          onMouseEnter={e => { e.currentTarget.style.background = TOKENS.bg.selected; }}
          onMouseLeave={e => { e.currentTarget.style.background = TOKENS.bg.xlightBg; }}
        >
          ⚖ Registrar Lei
        </button>
      </div>
    </div>
  );
}


// =============================================================================
// COMPONENTE: BadgeSituacao
// =============================================================================

function BadgeSituacao({ situacao }) {
  const styles = {
    'Em vigor':  { bg: TOKENS.blue.xlightBg,      color: TOKENS.blue.primary },
    'Extinto':   { bg: TOKENS.status.extinctoBg,   color: TOKENS.status.extinctoText },
    'Revogado':  { bg: TOKENS.status.dangerBg,     color: TOKENS.status.dangerText },
  };
  const s = styles[situacao] || styles['Em vigor'];
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 8px',
                   borderRadius: 999, fontSize: 11, fontWeight: 600,
                   background: s.bg, color: s.color }}>
      {situacao}
    </span>
  );
}


// =============================================================================
// COMPONENTE: SaldoBadge
// Exibe o saldo calculado com cor semântica
// =============================================================================

function SaldoBadge({ saldo }) {
  let bg, color;
  if (saldo > 0)       { bg = TOKENS.status.successBg; color = TOKENS.status.successText; }
  else if (saldo < 0)  { bg = TOKENS.status.dangerBg;  color = TOKENS.status.dangerText; }
  else                 { bg = TOKENS.status.warningBg;  color = TOKENS.status.warningText; }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', padding: '3px 10px',
                   borderRadius: 999, fontSize: 12, fontWeight: 700,
                   background: bg, color: color, minWidth: 36, justifyContent: 'center' }}>
      {saldo > 0 ? '+' : ''}{saldo}
    </span>
  );
}


// =============================================================================
// COMPONENTE: CargosTable
// Tabela principal dos cargos com saldo computado
// =============================================================================

const COLUNAS = [
  { key: 'nome',            label: 'Cargo',            width: 260 },
  { key: 'codigo_fopag',    label: 'Cód. FOPAG',       width: 90 },
  { key: 'situacao',        label: 'Situação',          width: 100 },
  { key: 'tipo_provimento', label: 'Provimento',        width: 100 },
  { key: 'carga_horaria',   label: 'CH (h)',            width: 70 },
  { key: 'total_previstos', label: 'Previstos',         width: 80 },
  { key: 'total_ocupados',  label: 'Ocupados',          width: 80 },
  { key: 'saldo_vagas',     label: 'Saldo',             width: 80 },
  { key: 'acoes',           label: '',                  width: 60 },
];

function CargosTable({ cargos, onAcao }) {
  const [sortKey, setSortKey]   = useState('nome');
  const [sortDir, setSortDir]   = useState('asc');
  const [selected, setSelected] = useState(null);

  const sorted = useMemo(() => {
    return [...cargos].sort((a, b) => {
      const va = a[sortKey] ?? '';
      const vb = b[sortKey] ?? '';
      const cmp = typeof va === 'number'
        ? va - vb
        : String(va).localeCompare(String(vb), 'pt-BR');
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [cargos, sortKey, sortDir]);

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };

  return (
    <div style={{ margin: '20px 32px 32px', border: `1px solid ${TOKENS.border.default}`,
                  borderRadius: 12, overflow: 'hidden', background: TOKENS.bg.card }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'inherit' }}>
          <thead>
            <tr style={{ background: TOKENS.bg.sidebar }}>
              {COLUNAS.map(col => (
                <th key={col.key}
                    onClick={() => col.key !== 'acoes' && handleSort(col.key)}
                    style={{ ...{}, padding: '12px 16px', textAlign: 'left', fontSize: 11,
                             fontWeight: 700, color: TOKENS.text.secondary, letterSpacing: '0.05em',
                             textTransform: 'uppercase', whiteSpace: 'nowrap', width: col.width,
                             cursor: col.key !== 'acoes' ? 'pointer' : 'default',
                             userSelect: 'none', borderBottom: `1px solid ${TOKENS.border.default}`,
                             transition: 'color 0.1s' }}
                    onMouseEnter={e => { if (col.key !== 'acoes') e.currentTarget.style.color = TOKENS.blue.primary; }}
                    onMouseLeave={e => e.currentTarget.style.color = TOKENS.text.secondary}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span style={{ marginLeft: 4, color: TOKENS.blue.primary }}>
                      {sortDir === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr>
                <td colSpan={COLUNAS.length}
                    style={{ padding: '48px 16px', textAlign: 'center',
                             color: TOKENS.text.muted, fontSize: 13 }}>
                  Nenhum cargo encontrado para os filtros selecionados.
                </td>
              </tr>
            )}
            {sorted.map((cargo, i) => {
              const isSelected = selected === cargo.id;
              const isAlta     = i % 2 === 0;
              return (
                <tr key={cargo.id}
                    onClick={() => setSelected(isSelected ? null : cargo.id)}
                    style={{ background: isSelected ? TOKENS.bg.selected
                                       : isAlta     ? TOKENS.bg.page
                                                    : TOKENS.bg.sidebar,
                             cursor: 'pointer', transition: 'background 0.1s',
                             borderBottom: `1px solid ${TOKENS.border.default}` }}
                    onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = TOKENS.bg.hover; }}
                    onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = isAlta ? TOKENS.bg.page : TOKENS.bg.sidebar; }}
                >
                  {/* Nome do cargo */}
                  <td style={{ padding: '12px 16px', fontSize: 13, color: TOKENS.text.primary,
                                fontWeight: 500, maxWidth: 260 }}>
                    <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis',
                                   whiteSpace: 'nowrap', maxWidth: 244 }}>
                      {cargo.nome}
                    </span>
                  </td>

                  {/* Código FOPAG */}
                  <td style={{ padding: '12px 16px', fontSize: 12, color: TOKENS.text.secondary,
                                fontFamily: 'monospace' }}>
                    {cargo.codigo_fopag || '—'}
                  </td>

                  {/* Situação */}
                  <td style={{ padding: '12px 16px' }}>
                    <BadgeSituacao situacao={cargo.situacao} />
                  </td>

                  {/* Tipo de provimento */}
                  <td style={{ padding: '12px 16px', fontSize: 12, color: TOKENS.text.secondary }}>
                    {cargo.tipo_provimento}
                  </td>

                  {/* Carga horária */}
                  <td style={{ padding: '12px 16px', fontSize: 12, color: TOKENS.text.secondary,
                                textAlign: 'center' }}>
                    {cargo.carga_horaria ? `${cargo.carga_horaria}h` : '—'}
                  </td>

                  {/* Total previstos */}
                  <td style={{ padding: '12px 16px', fontSize: 13, fontWeight: 600,
                                color: TOKENS.text.primary, textAlign: 'center' }}>
                    {cargo.total_previstos}
                  </td>

                  {/* Total ocupados */}
                  <td style={{ padding: '12px 16px', fontSize: 13,
                                color: TOKENS.text.secondary, textAlign: 'center' }}>
                    {cargo.total_ocupados}
                  </td>

                  {/* Saldo — badge semântico calculado */}
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <SaldoBadge saldo={cargo.total_previstos - cargo.total_ocupados} />
                  </td>

                  {/* Ações */}
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <button
                      onClick={e => { e.stopPropagation(); onAcao(cargo); }}
                      title="Ver detalhes / Registrar lei"
                      style={{ padding: '4px 8px', borderRadius: 6, border: 'none',
                                cursor: 'pointer', background: 'transparent', fontSize: 14,
                                color: TOKENS.blue.light, transition: 'background 0.1s' }}
                      onMouseEnter={e => e.currentTarget.style.background = TOKENS.bg.hover}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      ···
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Rodapé da tabela */}
      <div style={{ padding: '12px 16px', borderTop: `1px solid ${TOKENS.border.default}`,
                    background: TOKENS.bg.sidebar, display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: TOKENS.text.muted }}>
          {sorted.length} registro{sorted.length !== 1 ? 's' : ''}
        </span>
        <span style={{ fontSize: 11, color: TOKENS.text.muted }}>
          Saldo calculado em tempo real · Sistema FOPAG
        </span>
      </div>
    </div>
  );
}


// =============================================================================
// COMPONENTE: LeiModal
// Modal para registrar uma lei e aplicar seu impacto sobre o quadro
// =============================================================================

function LeiModal({ cargo, onClose, onSubmit }) {
  const [form, setForm] = useState({
    numero: '', ano: new Date().getFullYear(), acao: 'Cria',
    quantidade: '', descricao: '',
  });

  const ACOES_COM_QTD = new Set(['Cria', 'Extingue', 'Fixa']);

  const handleChange = (field, value) => setForm(f => ({ ...f, [field]: value }));

  const handleSubmit = () => {
    if (!form.numero || !form.ano || !form.acao) {
      alert('Preencha: número da lei, ano e ação.');
      return;
    }
    if (ACOES_COM_QTD.has(form.acao) && !form.quantidade) {
      alert(`A ação "${form.acao}" exige o campo Quantidade.`);
      return;
    }
    onSubmit({
      ...form,
      ano:       parseInt(form.ano, 10),
      quantidade: form.quantidade ? parseInt(form.quantidade, 10) : null,
    });
    onClose();
  };

  const inputStyle = {
    width: '100%', padding: '8px 12px', fontSize: 13, borderRadius: 8,
    border: `1px solid ${TOKENS.border.default}`, background: TOKENS.bg.input,
    color: TOKENS.text.primary, fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box',
  };

  const labelStyle = { fontSize: 11, fontWeight: 600, color: TOKENS.text.secondary,
                        textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block',
                        marginBottom: 6 };

  return (
    // Overlay
    <div onClick={onClose}
         style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 1000,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  backdropFilter: 'blur(2px)' }}>
      <div onClick={e => e.stopPropagation()}
           style={{ background: '#fff', borderRadius: 16, padding: '32px', width: 480,
                    maxWidth: '95vw', boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}>

        {/* Cabeçalho do modal */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                      marginBottom: 24 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: TOKENS.text.primary }}>
              Registrar Lei Pertinente
            </h2>
            {cargo && (
              <p style={{ margin: '4px 0 0', fontSize: 12, color: TOKENS.text.secondary }}>
                Cargo: <strong>{cargo.nome}</strong>
              </p>
            )}
          </div>
          <button onClick={onClose}
                  style={{ border: 'none', background: 'transparent', fontSize: 20,
                           cursor: 'pointer', color: TOKENS.text.muted, padding: 4,
                           borderRadius: 6, lineHeight: 1 }}>
            ×
          </button>
        </div>

        {/* Formulário */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Número e Ano lado a lado */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={labelStyle}>Número da Lei</label>
              <input style={inputStyle} placeholder="ex: 2194"
                     value={form.numero} onChange={e => handleChange('numero', e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Ano</label>
              <input style={inputStyle} type="number" placeholder="ex: 2024"
                     value={form.ano} onChange={e => handleChange('ano', e.target.value)} />
            </div>
          </div>

          {/* Ação */}
          <div>
            <label style={labelStyle}>Ação Disparada</label>
            <select style={{ ...inputStyle, cursor: 'pointer' }}
                    value={form.acao} onChange={e => handleChange('acao', e.target.value)}>
              {['Cria', 'Extingue', 'Fixa', 'Altera', 'Regulamenta', 'Outro'].map(a => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>

          {/* Quantidade — só aparece para ações numéricas */}
          {ACOES_COM_QTD.has(form.acao) && (
            <div>
              <label style={labelStyle}>
                Quantidade de Vagas
                <span style={{ color: TOKENS.blue.light, marginLeft: 4 }}>
                  ({form.acao === 'Fixa' ? 'valor absoluto final' : form.acao === 'Cria' ? 'incremento' : 'decremento'})
                </span>
              </label>
              <input style={inputStyle} type="number" min="0" placeholder="ex: 3"
                     value={form.quantidade} onChange={e => handleChange('quantidade', e.target.value)} />
            </div>
          )}

          {/* Descrição / ementa */}
          <div>
            <label style={labelStyle}>Descrição / Ementa</label>
            <textarea style={{ ...inputStyle, height: 72, resize: 'vertical' }}
                      placeholder="Descrição resumida da lei..."
                      value={form.descricao} onChange={e => handleChange('descricao', e.target.value)} />
          </div>

          {/* Preview do impacto */}
          {ACOES_COM_QTD.has(form.acao) && form.quantidade && cargo && (
            <div style={{ padding: '12px 16px', borderRadius: 8, background: TOKENS.bg.xlightBg,
                          border: `1px solid ${TOKENS.blue.xlight}` }}>
              <p style={{ margin: 0, fontSize: 12, color: TOKENS.blue.dark }}>
                <strong>Impacto calculado:</strong> Total previstos passa de&nbsp;
                <strong>{cargo.total_previstos}</strong> para&nbsp;
                <strong>
                  {form.acao === 'Cria'
                    ? cargo.total_previstos + parseInt(form.quantidade || 0, 10)
                    : form.acao === 'Extingue'
                      ? Math.max(0, cargo.total_previstos - parseInt(form.quantidade || 0, 10))
                      : parseInt(form.quantidade || 0, 10)}
                </strong>.
                Saldo passará para&nbsp;
                <strong>
                  {(form.acao === 'Cria'
                    ? cargo.total_previstos + parseInt(form.quantidade || 0, 10)
                    : form.acao === 'Extingue'
                      ? Math.max(0, cargo.total_previstos - parseInt(form.quantidade || 0, 10))
                      : parseInt(form.quantidade || 0, 10)) - cargo.total_ocupados}
                </strong>.
              </p>
            </div>
          )}
        </div>

        {/* Botões de ação */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 24 }}>
          <button onClick={onClose}
                  style={{ padding: '8px 20px', fontSize: 13, fontWeight: 500, borderRadius: 8,
                           border: `1px solid ${TOKENS.border.default}`, background: 'transparent',
                           cursor: 'pointer', color: TOKENS.text.secondary, fontFamily: 'inherit' }}>
            Cancelar
          </button>
          <button onClick={handleSubmit}
                  style={{ padding: '8px 20px', fontSize: 13, fontWeight: 600, borderRadius: 8,
                           border: 'none', cursor: 'pointer', background: TOKENS.blue.primary,
                           color: '#fff', fontFamily: 'inherit', transition: 'background 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = TOKENS.blue.primaryHover}
                  onMouseLeave={e => e.currentTarget.style.background = TOKENS.blue.primary}>
            Registrar Lei
          </button>
        </div>
      </div>
    </div>
  );
}


// =============================================================================
// COMPONENTE RAIZ: App
// Orquestra estado global e compõe o layout completo
// =============================================================================

// Dados de demonstração (em produção, viriam via IPC/API do processo Electron)
const MOCK_CARGOS = [
  { id: 1,  nome: 'Advogado do CREAS',             codigo_fopag: '409',  situacao: 'Em vigor', tipo_provimento: 'Efetivo',  carga_horaria: '20', total_previstos: 1,  total_ocupados: 1  },
  { id: 2,  nome: 'Agente Comunitário de Saúde - CEHAB', codigo_fopag: '1025', situacao: 'Em vigor', tipo_provimento: 'Efetivo', carga_horaria: '40', total_previstos: 6, total_ocupados: 6 },
  { id: 3,  nome: 'Agente Comunitário de Saúde - Cruzeiro', codigo_fopag: '1026', situacao: 'Em vigor', tipo_provimento: 'Efetivo', carga_horaria: '40', total_previstos: 5, total_ocupados: 4 },
  { id: 4,  nome: 'Agente Comunitário de Saúde - Jardim Bervely', codigo_fopag: '1023', situacao: 'Em vigor', tipo_provimento: 'Efetivo', carga_horaria: '40', total_previstos: 0, total_ocupados: 5 },
  { id: 5,  nome: 'Auditor Fiscal de Tributos',    codigo_fopag: '215',  situacao: 'Em vigor', tipo_provimento: 'Efetivo',  carga_horaria: '40', total_previstos: 8,  total_ocupados: 5  },
  { id: 6,  nome: 'Assessor de Governo',           codigo_fopag: '501',  situacao: 'Extinto',  tipo_provimento: 'Comissão', carga_horaria: '40', total_previstos: 0,  total_ocupados: 0  },
  { id: 7,  nome: 'Contador',                      codigo_fopag: '310',  situacao: 'Em vigor', tipo_provimento: 'Efetivo',  carga_horaria: '40', total_previstos: 3,  total_ocupados: 2  },
  { id: 8,  nome: 'Enfermeiro',                    codigo_fopag: '620',  situacao: 'Em vigor', tipo_provimento: 'Efetivo',  carga_horaria: '40', total_previstos: 12, total_ocupados: 10 },
  { id: 9,  nome: 'Fiscal de Obras',               codigo_fopag: '418',  situacao: 'Em vigor', tipo_provimento: 'Efetivo',  carga_horaria: '40', total_previstos: 4,  total_ocupados: 4  },
  { id: 10, nome: 'Guarda Civil Municipal',         codigo_fopag: '780',  situacao: 'Em vigor', tipo_provimento: 'Efetivo',  carga_horaria: '40', total_previstos: 30, total_ocupados: 22 },
];

export default function App() {
  const [activeNav, setActiveNav]     = useState('quadro');
  const [searchTerm, setSearchTerm]   = useState('');
  const [filtros, setFiltros]         = useState({ situacao: 'Todos', tipo: 'Todos' });
  const [cargos, setCargos]           = useState(MOCK_CARGOS);
  const [modalLei, setModalLei]       = useState(null);   // cargo selecionado para lei
  const [modalOpen, setModalOpen]     = useState(false);  // modal de lei aberto

  // Filtragem reativa
  const cargosFiltrados = useMemo(() => {
    return cargos.filter(c => {
      const matchSearch = !searchTerm || (
        c.nome.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (c.codigo_fopag || '').includes(searchTerm)
      );
      const matchSituacao = filtros.situacao === 'Todos' || c.situacao === filtros.situacao;
      const matchTipo     = filtros.tipo === 'Todos'     || c.tipo_provimento === filtros.tipo;
      return matchSearch && matchSituacao && matchTipo;
    });
  }, [cargos, searchTerm, filtros]);

  // KPIs derivados
  const kpis = useMemo(() => ({
    totalPrevistos: cargos.reduce((a, c) => a + c.total_previstos, 0),
    totalOcupados:  cargos.reduce((a, c) => a + c.total_ocupados,  0),
    totalSaldo:     cargos.reduce((a, c) => a + (c.total_previstos - c.total_ocupados), 0),
    alertas:        cargos.filter(c => (c.total_previstos - c.total_ocupados) < 0).length,
  }), [cargos]);

  // Registrar uma lei e aplicar impacto (mock — em produção chama IPC Electron)
  const handleRegistrarLei = useCallback((dados) => {
    if (!modalLei) return;
    setCargos(prev => prev.map(c => {
      if (c.id !== modalLei.id) return c;
      let novoPrevistos = c.total_previstos;
      if (dados.acao === 'Cria')     novoPrevistos = c.total_previstos + dados.quantidade;
      if (dados.acao === 'Extingue') novoPrevistos = Math.max(0, c.total_previstos - dados.quantidade);
      if (dados.acao === 'Fixa')     novoPrevistos = dados.quantidade;
      return { ...c, total_previstos: novoPrevistos };
    }));
  }, [modalLei]);

  return (
    <div style={{ display: 'flex', minHeight: '100vh', fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
                  background: TOKENS.bg.page, color: TOKENS.text.primary }}>

      {/* Sidebar */}
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />

      {/* Conteúdo principal */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

        {/* Header */}
        <Header
          searchTerm={searchTerm}
          onSearch={setSearchTerm}
          onNovoCargo={() => alert('Formulário de novo cargo — implementar')}
        />

        {/* KPIs */}
        <StatsBar dados={kpis} />

        {/* Toolbar de filtros */}
        <TableToolbar
          filtros={filtros}
          onChange={setFiltros}
          totalFiltrado={cargosFiltrados.length}
          onRegistrarLei={() => { setModalLei(null); setModalOpen(true); }}
        />

        {/* Tabela principal */}
        <CargosTable
          cargos={cargosFiltrados}
          onAcao={(cargo) => { setModalLei(cargo); setModalOpen(true); }}
        />
      </div>

      {/* Modal de lei */}
      {modalOpen && (
        <LeiModal
          cargo={modalLei}
          onClose={() => { setModalOpen(false); setModalLei(null); }}
          onSubmit={handleRegistrarLei}
        />
      )}
    </div>
  );
}
