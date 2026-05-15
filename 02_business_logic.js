/**
 * =============================================================================
 * SISTEMA DE GESTÃO DE CARGOS E VAGAS (FOPAG) — Prefeitura de Miracema
 * Arquivo: 02_business_logic.js
 * Runtime: Node.js (compatible com Electron main process)
 * Dependência: better-sqlite3  →  npm install better-sqlite3
 *
 * Motor de Regras de Negócio: Saldo de Vagas
 * Responsabilidade:
 *   - Calcular o saldo em tempo real (nunca persistido como coluna estática)
 *   - Validar e persistir o impacto de novas leis sobre o quadro de vagas
 *   - Garantir rastreabilidade total das alterações via LeisPertinentes
 * =============================================================================
 */

'use strict';

const Database = require('better-sqlite3');
const path     = require('path');

// ---------------------------------------------------------------------------
// CONFIGURAÇÃO DO BANCO
// O arquivo .db é mantido na pasta de dados do app (Electron userData)
// ---------------------------------------------------------------------------

const DB_PATH = path.join(
  process.env.APPDATA || process.env.HOME,
  'fopag-sistema',
  'quadro_pessoal.db'
);

/**
 * Abre (ou cria) a conexão com o SQLite.
 * Habilita foreign keys — obrigatório no SQLite.
 * @returns {Database} instância do banco
 */
function abrirBanco() {
  const db = new Database(DB_PATH, { verbose: null });
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  return db;
}


// =============================================================================
// MÓDULO 1 — CONSULTA DE SALDO
// Sempre lê o saldo via view computada (vw_SaldoVagas), nunca de coluna estática
// =============================================================================

/**
 * Retorna o saldo atual de vagas para um cargo específico.
 * Saldo = total_previstos − total_ocupados  (calculado pela VIEW)
 *
 * @param {number} cargoId
 * @returns {{ saldo_vagas: number, total_previstos: number, total_ocupados: number, alerta_saldo_negativo: 0|1 }}
 */
function getSaldoPorCargo(cargoId) {
  const db = abrirBanco();
  try {
    const row = db
      .prepare(`
        SELECT
          id,
          nome,
          total_previstos,
          total_ocupados,
          saldo_vagas,
          alerta_saldo_negativo
        FROM vw_SaldoVagas
        WHERE id = ?
      `)
      .get(cargoId);

    if (!row) throw new Error(`Cargo com id=${cargoId} não encontrado.`);
    return row;
  } finally {
    db.close();
  }
}

/**
 * Retorna a listagem completa do quadro com saldos calculados.
 * Suporta filtros opcionais por situação e tipo de provimento.
 *
 * @param {{ situacao?: string, tipo_provimento?: string }} filtros
 * @returns {Array<Object>}
 */
function listarSaldos(filtros = {}) {
  const db = abrirBanco();
  try {
    let sql = 'SELECT * FROM vw_SaldoVagas WHERE 1=1';
    const params = [];

    if (filtros.situacao) {
      sql += ' AND situacao = ?';
      params.push(filtros.situacao);
    }
    if (filtros.tipo_provimento) {
      sql += ' AND tipo_provimento = ?';
      params.push(filtros.tipo_provimento);
    }

    sql += ' ORDER BY nome ASC';
    return db.prepare(sql).all(...params);
  } finally {
    db.close();
  }
}


// =============================================================================
// MÓDULO 2 — MOTOR DE IMPACTO DE LEIS
// Coração da regra de negócio: ao registrar uma lei, o sistema recalcula
// total_previstos do cargo e registra o evento em LeisPertinentes.
// =============================================================================

/**
 * Mapa de ações que produzem impacto numérico no quadro de vagas.
 * Ações fora deste mapa são puramente qualitativas (Altera, Regulamenta, Outro).
 */
const ACOES_COM_IMPACTO = new Set(['Cria', 'Extingue', 'Fixa']);

/**
 * Analisa o texto bruto da célula da planilha e tenta extrair
 * a ação e a quantidade.
 *
 * Padrões reconhecidos (baseados na planilha real):
 *   "Cria 5"              → { acao: 'Cria',    quantidade: 5 }
 *   "Cria +1; Totaliza 6" → { acao: 'Cria',    quantidade: 1 }
 *   "Extingue 25"         → { acao: 'Extingue', quantidade: 25 }
 *   "Fixa em 5"           → { acao: 'Fixa',     quantidade: 5 }
 *   "Totaliza 5"          → { acao: 'Fixa',     quantidade: 5 }
 *   "Aumenta para 250"    → { acao: 'Fixa',     quantidade: 250 }
 *   "Altera ..."          → { acao: 'Altera',   quantidade: null }
 *   "Regulamenta ..."     → { acao: 'Regulamenta', quantidade: null }
 *
 * @param {string} texto
 * @returns {{ acao: string, quantidade: number|null, textoOriginal: string }}
 */
function parsearTextoCelula(texto) {
  if (!texto || typeof texto !== 'string') {
    return { acao: 'Outro', quantidade: null, textoOriginal: texto };
  }

  const t = texto.trim();

  // "Cria +N" ou "Cria N"
  let m = t.match(/^Cria\s+\+?(\d+)/i);
  if (m) return { acao: 'Cria', quantidade: parseInt(m[1], 10), textoOriginal: t };

  // "Extingue N"
  m = t.match(/^Extingue\s+(\d+)/i);
  if (m) return { acao: 'Extingue', quantidade: parseInt(m[1], 10), textoOriginal: t };

  // "Fixa em N" ou "Fixa N"
  m = t.match(/^Fixa\s+(?:em\s+)?(\d+)/i);
  if (m) return { acao: 'Fixa', quantidade: parseInt(m[1], 10), textoOriginal: t };

  // "Totaliza N" — equivalente a fixar o total previsto
  m = t.match(/Totaliza\s+(\d+)/i);
  if (m) return { acao: 'Fixa', quantidade: parseInt(m[1], 10), textoOriginal: t };

  // "Aumenta para N"
  m = t.match(/Aumenta\s+para\s+(\d+)/i);
  if (m) return { acao: 'Fixa', quantidade: parseInt(m[1], 10), textoOriginal: t };

  // "Altera ..."
  if (/^Altera/i.test(t)) return { acao: 'Altera', quantidade: null, textoOriginal: t };

  // "Regulamenta ..."
  if (/^Regulamenta/i.test(t)) return { acao: 'Regulamenta', quantidade: null, textoOriginal: t };

  // Texto livre sem padrão reconhecido — preserva para auditoria
  return { acao: 'Outro', quantidade: null, textoOriginal: t };
}

/**
 * Registra uma nova Lei Pertinente para um cargo e aplica seu impacto
 * automático sobre total_previstos.
 *
 * Esta função é a ÚNICA via autorizada para alterar total_previstos via lei.
 * Toda operação é atômica (transação SQLite).
 *
 * @param {number}  cargoId      - ID do cargo afetado
 * @param {string}  numero       - número da lei (ex: "2194")
 * @param {number}  ano          - ano da lei (ex: 2024)
 * @param {string}  acao         - 'Cria' | 'Extingue' | 'Fixa' | 'Altera' | 'Regulamenta' | 'Outro'
 * @param {number|null} quantidade - vagas criadas/extintas/fixadas (null para ações qualitativas)
 * @param {string}  [descricao]  - ementa / observações
 * @param {string}  [textoOriginal] - célula bruta da planilha (auditoria)
 * @returns {{ success: boolean, saldoAnterior: number, saldoNovo: number, lei: Object }}
 */
function registrarLeiEAplicarImpacto({
  cargoId,
  numero,
  ano,
  acao,
  quantidade,
  descricao    = null,
  textoOriginal = null,
}) {
  // Validações de entrada
  if (!cargoId || !numero || !ano || !acao) {
    throw new Error('cargoId, numero, ano e acao são obrigatórios.');
  }

  const ACOES_VALIDAS = ['Cria', 'Extingue', 'Fixa', 'Altera', 'Regulamenta', 'Outro'];
  if (!ACOES_VALIDAS.includes(acao)) {
    throw new Error(`Ação "${acao}" inválida. Opções: ${ACOES_VALIDAS.join(', ')}`);
  }

  if (ACOES_COM_IMPACTO.has(acao) && (quantidade === null || quantidade === undefined)) {
    throw new Error(`Ação "${acao}" exige o campo "quantidade".`);
  }

  const db = abrirBanco();

  try {
    // Executa tudo em uma única transação atômica
    const resultado = db.transaction(() => {

      // 1. Lê o estado atual do cargo para auditoria
      const cargoAtual = db.prepare(
        'SELECT id, nome, total_previstos, total_ocupados FROM Cargos WHERE id = ?'
      ).get(cargoId);

      if (!cargoAtual) throw new Error(`Cargo id=${cargoId} não encontrado.`);

      const saldoAnterior = cargoAtual.total_previstos - cargoAtual.total_ocupados;

      // 2. Calcula o novo total_previstos conforme a ação
      let novoTotalPrevistos = cargoAtual.total_previstos;

      if (acao === 'Cria') {
        novoTotalPrevistos = cargoAtual.total_previstos + quantidade;
      } else if (acao === 'Extingue') {
        novoTotalPrevistos = Math.max(0, cargoAtual.total_previstos - quantidade);
      } else if (acao === 'Fixa') {
        // 'Fixa' substitui o total previsto pelo valor absoluto informado
        novoTotalPrevistos = quantidade;
      }
      // Ações qualitativas (Altera, Regulamenta, Outro) não alteram o quantitativo

      // 3. Atualiza o cargo (apenas se houve mudança numérica)
      if (novoTotalPrevistos !== cargoAtual.total_previstos) {
        db.prepare(
          'UPDATE Cargos SET total_previstos = ? WHERE id = ?'
        ).run(novoTotalPrevistos, cargoId);
      }

      // 4. Registra o evento na tabela histórica
      const insertLei = db.prepare(`
        INSERT INTO LeisPertinentes
          (cargo_id, numero, ano, descricao, acao, quantidade, texto_original)
        VALUES
          (?, ?, ?, ?, ?, ?, ?)
      `);

      const info = insertLei.run(
        cargoId,
        numero,
        ano,
        descricao,
        acao,
        ACOES_COM_IMPACTO.has(acao) ? quantidade : null,
        textoOriginal
      );

      // 5. Calcula saldo final para retornar ao chamador
      const saldoNovo = novoTotalPrevistos - cargoAtual.total_ocupados;

      return {
        success:       true,
        cargoId:       cargoId,
        cargoNome:     cargoAtual.nome,
        saldoAnterior: saldoAnterior,
        saldoNovo:     saldoNovo,
        lei: {
          id:             info.lastInsertRowid,
          numero:         numero,
          ano:            ano,
          acao:           acao,
          quantidade:     quantidade,
          impactoNeto:    novoTotalPrevistos - cargoAtual.total_previstos,
        },
      };

    })(); // auto-executa a transação

    return resultado;

  } finally {
    db.close();
  }
}


// =============================================================================
// MÓDULO 3 — ATUALIZAÇÃO DIRETA DE OCUPADOS
// Quando uma nomeação ou exoneração é registrada, atualiza total_ocupados.
// O saldo é recalculado automaticamente pela VIEW.
// =============================================================================

/**
 * Atualiza a quantidade de vagas ocupadas para um cargo.
 * Pode ser um valor absoluto ou um delta (+/-).
 *
 * @param {number} cargoId
 * @param {'absoluto'|'delta'} modo  - 'absoluto' substitui; 'delta' soma/subtrai
 * @param {number} valor             - novo total (modo absoluto) ou variação (modo delta)
 * @returns {{ saldoNovo: number }}
 */
function atualizarOcupados(cargoId, modo, valor) {
  const db = abrirBanco();
  try {
    const cargo = db.prepare('SELECT total_previstos, total_ocupados FROM Cargos WHERE id = ?').get(cargoId);
    if (!cargo) throw new Error(`Cargo id=${cargoId} não encontrado.`);

    let novoOcupados;
    if (modo === 'absoluto') {
      novoOcupados = Math.max(0, valor);
    } else if (modo === 'delta') {
      novoOcupados = Math.max(0, cargo.total_ocupados + valor);
    } else {
      throw new Error('modo deve ser "absoluto" ou "delta".');
    }

    db.prepare('UPDATE Cargos SET total_ocupados = ? WHERE id = ?').run(novoOcupados, cargoId);

    return { saldoNovo: cargo.total_previstos - novoOcupados };
  } finally {
    db.close();
  }
}


// =============================================================================
// MÓDULO 4 — RESUMO ESTATÍSTICO DO QUADRO
// Para o painel/dashboard da tela principal
// =============================================================================

/**
 * Retorna estatísticas agregadas do quadro de pessoal.
 * @returns {{ totalCargos, totalPrevistos, totalOcupados, totalSaldo, cargosComAlerta }}
 */
function getResumoQuadro() {
  const db = abrirBanco();
  try {
    return db.prepare(`
      SELECT
        COUNT(*)                                  AS total_cargos,
        SUM(total_previstos)                      AS total_previstos,
        SUM(total_ocupados)                       AS total_ocupados,
        SUM(saldo_vagas)                          AS total_saldo,
        SUM(alerta_saldo_negativo)                AS cargos_com_alerta,
        SUM(CASE situacao WHEN 'Em vigor'  THEN 1 ELSE 0 END) AS cargos_em_vigor,
        SUM(CASE situacao WHEN 'Extinto'   THEN 1 ELSE 0 END) AS cargos_extintos,
        SUM(CASE tipo_provimento WHEN 'Efetivo'  THEN 1 ELSE 0 END) AS cargos_efetivos,
        SUM(CASE tipo_provimento WHEN 'Comissão' THEN 1 ELSE 0 END) AS cargos_comissao
      FROM vw_SaldoVagas
    `).get();
  } finally {
    db.close();
  }
}


// =============================================================================
// EXPORTAÇÕES (padrão CommonJS para compatibilidade com Electron)
// =============================================================================

module.exports = {
  // Consultas
  getSaldoPorCargo,
  listarSaldos,
  getResumoQuadro,

  // Motor de regras
  registrarLeiEAplicarImpacto,
  parsearTextoCelula,

  // Operações diretas
  atualizarOcupados,
};


// =============================================================================
// EXEMPLO DE USO (executar com: node 02_business_logic.js)
// =============================================================================

if (require.main === module) {
  console.log('\n=== TESTE DO MOTOR DE SALDO ===\n');

  // Exemplo: Lei 2194/2024 cria vagas de ACS
  const resultado = registrarLeiEAplicarImpacto({
    cargoId:       1,        // ID do cargo na tabela Cargos
    numero:        '2194',
    ano:           2024,
    acao:          'Cria',
    quantidade:    3,
    descricao:     'Cria cargos ACS',
    textoOriginal: 'Cria +3; Totaliza 9',
  });

  console.log('Resultado:', JSON.stringify(resultado, null, 2));

  // Exemplo: parsear célula da planilha legada
  const testes = [
    'Cria 5',
    'Cria +1; Totaliza 6',
    'Extingue 25',
    'Fixa em 5',
    'Totaliza 250',
    'Aumenta para 250',
    'Altera remuneração',
    'Regulamenta carga horária',
    'Plano de Cargos, Carreiras e Salários...',
  ];

  console.log('\n=== PARSER DE CÉLULAS ===');
  testes.forEach(t => {
    const r = parsearTextoCelula(t);
    console.log(`  "${t.substring(0,40)}" → acao=${r.acao}, qty=${r.quantidade}`);
  });
}
