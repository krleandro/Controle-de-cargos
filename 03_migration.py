"""
=============================================================================
SISTEMA DE GESTÃO DE CARGOS E VAGAS (FOPAG) — Prefeitura de Miracema
Arquivo: 03_migration.py
Runtime: Python 3.10+
Dependências: pip install pandas openpyxl

Estratégia de Migração / Ingestão de Dados
Responsabilidade:
  - Ler a planilha legada "CARGOS EFETIVOS E COMISSIONADOS - PMM - Ativos e extintos - 2026.xlsx"
  - Normalizar os dados em três tabelas relacionais:
      Cargos / FontesCargaHoraria / LeisPertinentes
  - Executar os INSERTs no banco SQLite criado pelo script 01_schema.sql
  - Gerar relatório de migração (linhas processadas, erros, alertas)

Estrutura da planilha legada:
  - 381 linhas de cargos
  - 13 colunas de dados principais (Cargo, Situação, Código FOPAG, etc.)
  - 215 colunas de leis pivoteadas horizontalmente (uma coluna por lei)
    com células contendo texto como "Cria 5", "Extingue 25", "Totaliza 6", etc.
=============================================================================
"""

import sqlite3
import pandas as pd
import re
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------------

# Ajuste estes caminhos conforme seu ambiente
XLSX_PATH = Path(r"C:\Users\Cliente\OneDrive\Documentos\Controle de cargos\CARGOS EFETIVOS E COMISSIONADOS - PMM - Ativos e extintos - 2026.xlsx")
DB_PATH   = Path(r"C:\Users\Cliente\OneDrive\Documentos\Controle de cargos\quadro_pessoal.db")
LOG_PATH  = Path(r"C:\Users\Cliente\OneDrive\Documentos\Controle de cargos\migracao_log.txt")

# Colunas estruturais da planilha (não são leis)
COLUNAS_PRINCIPAIS = {
    'Cargo', 'Situação', 'Código FOPAG', 'Tipo de Provimento',
    'Recrutamento', 'Restrição - Exigência', 'Carga Horária Semanal',
    'Fonte Carga Horária', 'Símbolo de Vencimento',
    'Total de cargos PREVISTOS', 'Total de cargos OCUPADOS',
    'SALDO TOTAL', 'Atribuições', 'Coluna1',
}

# Mapeamento das colunas da planilha → campos do banco
MAP_COLUNAS = {
    'Cargo':                      'nome',
    'Situação':                   'situacao',
    'Código FOPAG':               'codigo_fopag',
    'Tipo de Provimento':         'tipo_provimento',
    'Recrutamento':               'recrutamento',
    'Restrição - Exigência':      'escolaridade',
    'Carga Horária Semanal':      'carga_horaria',
    'Símbolo de Vencimento':      'simbolo_vencimento',
    'Total de cargos PREVISTOS':  'total_previstos',
    'Total de cargos OCUPADOS':   'total_ocupados',
    'Atribuições':                'atribuicoes',
}

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger('migracao_fopag')


# =============================================================================
# BLOCO 1 — PARSER DE CÉLULAS DE LEI
# Replica a lógica de parsearTextoCelula() do arquivo 02_business_logic.js
# para o contexto Python da migração.
# =============================================================================

def parsear_celula_lei(texto: str) -> dict:
    """
    Analisa o texto bruto de uma célula de lei e extrai:
      - acao: 'Cria', 'Extingue', 'Fixa', 'Altera', 'Regulamenta', 'Outro'
      - quantidade: int ou None

    Padrões reconhecidos:
      "Cria 5"              → Cria,    5
      "Cria +1; Totaliza 6" → Cria,    1
      "Extingue 25"         → Extingue, 25
      "Fixa em 5"           → Fixa,    5
      "Totaliza 5"          → Fixa,    5
      "Aumenta para 250"    → Fixa,    250
      "Altera ..."          → Altera,  None
      "Regulamenta ..."     → Regulamenta, None
      outros                → Outro,   None
    """
    if not isinstance(texto, str) or not texto.strip():
        return {'acao': 'Outro', 'quantidade': None}

    t = texto.strip()

    # Cria +N ou Cria N
    m = re.match(r'^Cria\s+\+?(\d+)', t, re.IGNORECASE)
    if m:
        return {'acao': 'Cria', 'quantidade': int(m.group(1))}

    # Extingue N
    m = re.match(r'^Extingue\s+(\d+)', t, re.IGNORECASE)
    if m:
        return {'acao': 'Extingue', 'quantidade': int(m.group(1))}

    # Fixa em N ou Fixa N
    m = re.match(r'^Fixa\s+(?:em\s+)?(\d+)', t, re.IGNORECASE)
    if m:
        return {'acao': 'Fixa', 'quantidade': int(m.group(1))}

    # Totaliza N → equivale a Fixa
    m = re.search(r'Totaliza\s+(\d+)', t, re.IGNORECASE)
    if m:
        return {'acao': 'Fixa', 'quantidade': int(m.group(1))}

    # Aumenta para N → equivale a Fixa
    m = re.match(r'^Aumenta\s+para\s+(\d+)', t, re.IGNORECASE)
    if m:
        return {'acao': 'Fixa', 'quantidade': int(m.group(1))}

    # Altera
    if re.match(r'^Altera', t, re.IGNORECASE):
        return {'acao': 'Altera', 'quantidade': None}

    # Regulamenta
    if re.match(r'^Regulamenta', t, re.IGNORECASE):
        return {'acao': 'Regulamenta', 'quantidade': None}

    # Plano de Cargos / Plano de Carreira (frequente na planilha)
    if re.match(r'^Plano\s+de', t, re.IGNORECASE):
        return {'acao': 'Regulamenta', 'quantidade': None}

    return {'acao': 'Outro', 'quantidade': None}


def extrair_numero_ano_lei(cabecalho: str) -> tuple[str, Optional[int]]:
    """
    Extrai número e ano do cabeçalho da coluna de lei.
    Exemplos de cabeçalhos:
      "813/99 - Plano de cargos..."  → ('813', 1999)
      "824/00"                       → ('824', 2000)
      "2194/2024 - Cria cargos ACS"  → ('2194', 2024)
      "Lei nº 2.275/2026"            → ('2275', 2026)
    """
    # Formato "NNNN/YY" ou "NNNN/YYYY"
    m = re.match(r'^[\w\s\.]*?(\d[\d\.]*)/([\d]{2,4})', cabecalho.strip())
    if m:
        numero_raw = m.group(1).replace('.', '')
        ano_raw    = m.group(2)
        numero     = numero_raw

        # Normaliza ano de 2 dígitos
        ano_int = int(ano_raw)
        if len(ano_raw) == 2:
            ano_int = 1900 + ano_int if ano_int >= 90 else 2000 + ano_int

        return numero, ano_int

    return cabecalho[:50], None


def sanitizar_carga_horaria(valor) -> Optional[str]:
    """Normaliza o campo de carga horária."""
    if pd.isna(valor):
        return None
    s = str(valor).strip()
    validos = {'10', '20', '25', '30', '40', '44'}
    # Tenta extrair número inteiro
    m = re.search(r'\b(\d+)\b', s)
    if m and m.group(1) in validos:
        return m.group(1)
    if s in ('Não regulamentada em lei', 'Verificar edital'):
        return s
    return None  # valor inválido — omitido


def sanitizar_situacao(valor) -> str:
    """Normaliza o campo situação."""
    if pd.isna(valor):
        return 'Em vigor'
    s = str(valor).strip()
    mapa = {
        'Em vigor':  'Em vigor',
        'Extinto':   'Extinto',
        'Revogado':  'Revogado',
        'Extintos':  'Extinto',
    }
    return mapa.get(s, 'Em vigor')


def sanitizar_int(valor, default=0) -> int:
    """Converte para int seguro."""
    try:
        return int(float(str(valor))) if not pd.isna(valor) else default
    except (ValueError, TypeError):
        return default


# =============================================================================
# BLOCO 2 — LEITURA E PRÉ-PROCESSAMENTO DA PLANILHA
# =============================================================================

def carregar_planilha() -> pd.DataFrame:
    """Carrega a planilha xlsx e realiza pré-processamento básico."""
    log.info(f"Lendo planilha: {XLSX_PATH}")
    df = pd.read_excel(XLSX_PATH, sheet_name='Planilha1', dtype=str)
    log.info(f"  → {len(df)} linhas × {len(df.columns)} colunas carregadas")

    # Remove linhas completamente vazias
    df = df.dropna(subset=['Cargo'])
    df = df[df['Cargo'].str.strip() != '']
    log.info(f"  → {len(df)} linhas com cargo preenchido")

    return df.reset_index(drop=True)


def identificar_colunas_leis(df: pd.DataFrame) -> list[str]:
    """Retorna lista de colunas que representam leis (tudo que não é coluna principal)."""
    cols_lei = [c for c in df.columns if c not in COLUNAS_PRINCIPAIS]
    log.info(f"  → {len(cols_lei)} colunas de leis identificadas")
    return cols_lei


# =============================================================================
# BLOCO 3 — EXTRAÇÃO DA FONTE DE CARGA HORÁRIA
# O campo "Fonte Carga Horária" é texto livre; tentamos estruturá-lo.
# Exemplos: "Edital 2023 - BO 375" / "Lei 1632/2016 e Lei Federal nº 13.708/18"
# =============================================================================

def parsear_fonte_carga_horaria(texto: str) -> list[dict]:
    """
    Tenta decompor o campo 'Fonte Carga Horária' em registros estruturados
    para a tabela FontesCargaHoraria.
    Retorna lista de dicts com { tipo, numero, ano, detalhes }.
    """
    if not isinstance(texto, str) or not texto.strip():
        return []

    fontes = []
    # Separa múltiplas fontes por " e " ou " / "
    partes = re.split(r'\s+e\s+|\s*/\s*', texto, flags=re.IGNORECASE)

    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue

        # Detecta Lei
        m = re.search(r'Lei\s+(?:Federal\s+)?(?:nº\s*)?(\d[\d\.]*)/(\d{2,4})', parte, re.IGNORECASE)
        if m:
            numero_raw = m.group(1).replace('.', '')
            ano_raw    = int(m.group(2))
            if len(m.group(2)) == 2:
                ano_raw = 1900 + ano_raw if ano_raw >= 90 else 2000 + ano_raw
            fontes.append({'tipo': 'Lei', 'numero': numero_raw, 'ano': ano_raw, 'detalhes': parte})
            continue

        # Detecta Edital
        m_edital = re.search(r'Edital\s+(\d+)', parte, re.IGNORECASE)
        if m_edital:
            fontes.append({'tipo': 'Edital', 'numero': m_edital.group(1), 'ano': None, 'detalhes': parte})
            continue

        # Genérico
        fontes.append({'tipo': 'Outro', 'numero': None, 'ano': None, 'detalhes': parte})

    return fontes


# =============================================================================
# BLOCO 4 — INSERÇÃO NO BANCO DE DADOS
# =============================================================================

def migrar_para_sqlite(df: pd.DataFrame, cols_lei: list[str]):
    """
    Orquestra toda a migração: cria conexão, insere Cargos,
    FontesCargaHoraria e LeisPertinentes.
    """
    if not DB_PATH.exists():
        log.error(f"Banco não encontrado: {DB_PATH}")
        log.error("Execute primeiro o script 01_schema.sql para criar o banco.")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()

    # Estatísticas
    stats = {
        'cargos_inseridos':    0,
        'cargos_erro':         0,
        'fontes_inseridas':    0,
        'leis_inseridas':      0,
        'leis_sem_acao':       0,
        'alertas_saldo':       0,
    }

    log.info("\n=== INICIANDO MIGRAÇÃO ===")
    inicio = datetime.now()

    for idx, row in df.iterrows():

        # ------------------------------------------------------------------
        # 4.1 — INSERIR CARGO
        # ------------------------------------------------------------------
        try:
            cargo_data = {
                'nome':             str(row.get('Cargo', '')).strip(),
                'codigo_fopag':     str(row.get('Código FOPAG', '')).strip() or None,
                'situacao':         sanitizar_situacao(row.get('Situação')),
                'tipo_provimento':  str(row.get('Tipo de Provimento', 'Efetivo')).strip(),
                'escolaridade':     str(row.get('Restrição - Exigência', '')).strip() or None,
                'carga_horaria':    sanitizar_carga_horaria(row.get('Carga Horária Semanal')),
                'simbolo_vencimento': str(row.get('Símbolo de Vencimento', '')).strip() or None,
                'total_previstos':  sanitizar_int(row.get('Total de cargos PREVISTOS'), 0),
                'total_ocupados':   sanitizar_int(row.get('Total de cargos OCUPADOS'), 0),
                'atribuicoes':      str(row.get('Atribuições', '')).strip() or None,
            }

            # Alerta: saldo negativo na planilha original
            saldo_original = sanitizar_int(row.get('SALDO TOTAL'), 0)
            if saldo_original < 0:
                stats['alertas_saldo'] += 1
                log.warning(f"  ⚠ Saldo negativo na planilha: cargo='{cargo_data['nome']}' saldo={saldo_original}")

            cur.execute("""
                INSERT INTO Cargos
                    (nome, codigo_fopag, situacao, tipo_provimento,
                     escolaridade, carga_horaria, simbolo_vencimento,
                     total_previstos, total_ocupados, atribuicoes)
                VALUES
                    (:nome, :codigo_fopag, :situacao, :tipo_provimento,
                     :escolaridade, :carga_horaria, :simbolo_vencimento,
                     :total_previstos, :total_ocupados, :atribuicoes)
            """, cargo_data)

            cargo_id = cur.lastrowid
            stats['cargos_inseridos'] += 1

        except sqlite3.IntegrityError as e:
            log.error(f"  ✗ Linha {idx+2}: erro ao inserir cargo '{row.get('Cargo')}': {e}")
            stats['cargos_erro'] += 1
            continue

        # ------------------------------------------------------------------
        # 4.2 — INSERIR FONTES DE CARGA HORÁRIA
        # ------------------------------------------------------------------
        fonte_texto = row.get('Fonte Carga Horária', '')
        if isinstance(fonte_texto, str) and fonte_texto.strip():
            fontes = parsear_fonte_carga_horaria(fonte_texto)
            for f in fontes:
                try:
                    cur.execute("""
                        INSERT INTO FontesCargaHoraria
                            (cargo_id, tipo, numero, ano, detalhes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (cargo_id, f['tipo'], f['numero'], f['ano'], f['detalhes']))
                    stats['fontes_inseridas'] += 1
                except Exception as e:
                    log.warning(f"    ⚠ FontesCH: cargo_id={cargo_id}: {e}")

        # ------------------------------------------------------------------
        # 4.3 — INSERIR LEIS PERTINENTES (colunas pivoteadas)
        # Cada coluna de lei é verificada: se a célula tiver valor, insere.
        # ------------------------------------------------------------------
        for col_lei in cols_lei:
            valor_celula = row.get(col_lei)

            # Ignora células vazias
            if pd.isna(valor_celula) or str(valor_celula).strip() in ('', 'nan'):
                continue

            texto_celula   = str(valor_celula).strip()
            numero_lei, ano_lei = extrair_numero_ano_lei(col_lei)
            descricao_lei  = col_lei  # o próprio cabeçalho contém a ementa
            parsed         = parsear_celula_lei(texto_celula)

            try:
                cur.execute("""
                    INSERT INTO LeisPertinentes
                        (cargo_id, numero, ano, descricao, acao, quantidade, texto_original)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    cargo_id,
                    numero_lei,
                    ano_lei,
                    descricao_lei,
                    parsed['acao'],
                    parsed['quantidade'],
                    texto_celula,
                ))
                stats['leis_inseridas'] += 1

                if parsed['acao'] == 'Outro':
                    stats['leis_sem_acao'] += 1

            except Exception as e:
                log.warning(f"    ⚠ Lei '{col_lei[:30]}', cargo_id={cargo_id}: {e}")

    # Commit final
    con.commit()
    con.close()

    duracao = (datetime.now() - inicio).total_seconds()

    log.info("\n=== MIGRAÇÃO CONCLUÍDA ===")
    log.info(f"  ✔ Cargos inseridos:      {stats['cargos_inseridos']}")
    log.info(f"  ✗ Cargos com erro:       {stats['cargos_erro']}")
    log.info(f"  ✔ Fontes CH inseridas:   {stats['fontes_inseridas']}")
    log.info(f"  ✔ Leis inseridas:        {stats['leis_inseridas']}")
    log.info(f"  ⚠ Leis sem ação clara:   {stats['leis_sem_acao']}")
    log.info(f"  ⚠ Alertas saldo negativo:{stats['alertas_saldo']}")
    log.info(f"  ⏱ Duração:              {duracao:.2f}s")

    return stats


# =============================================================================
# BLOCO 5 — VERIFICAÇÃO PÓS-MIGRAÇÃO
# Executa queries de sanidade para confirmar integridade dos dados migrados.
# =============================================================================

def verificar_migracao():
    """
    Realiza checks de sanidade no banco após a migração:
    - Conta registros por tabela
    - Verifica saldos negativos
    - Confirma que as FKs estão consistentes
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    log.info("\n=== VERIFICAÇÃO PÓS-MIGRAÇÃO ===")

    checks = [
        ("Total de cargos",                 "SELECT COUNT(*) FROM Cargos"),
        ("Cargos Em vigor",                 "SELECT COUNT(*) FROM Cargos WHERE situacao='Em vigor'"),
        ("Total de Leis Pertinentes",       "SELECT COUNT(*) FROM LeisPertinentes"),
        ("Total de Fontes Carga Horária",   "SELECT COUNT(*) FROM FontesCargaHoraria"),
        ("Cargos com saldo negativo",       "SELECT COUNT(*) FROM vw_SaldoVagas WHERE alerta_saldo_negativo=1"),
        ("Leis com ação 'Cria'",            "SELECT COUNT(*) FROM LeisPertinentes WHERE acao='Cria'"),
        ("Leis com ação 'Extingue'",        "SELECT COUNT(*) FROM LeisPertinentes WHERE acao='Extingue'"),
        ("Leis com ação 'Fixa'",            "SELECT COUNT(*) FROM LeisPertinentes WHERE acao='Fixa'"),
        ("Leis com ação 'Outro'",           "SELECT COUNT(*) FROM LeisPertinentes WHERE acao='Outro'"),
    ]

    for label, sql in checks:
        result = cur.execute(sql).fetchone()[0]
        log.info(f"  {label:<40}: {result}")

    # Top 5 cargos por total de leis vinculadas
    log.info("\n  Top 5 cargos com mais leis:")
    rows = cur.execute("""
        SELECT c.nome, COUNT(l.id) AS qtd_leis
        FROM   Cargos c
        JOIN   LeisPertinentes l ON l.cargo_id = c.id
        GROUP  BY c.id
        ORDER  BY qtd_leis DESC
        LIMIT  5
    """).fetchall()
    for r in rows:
        log.info(f"    {r['nome'][:50]:<50} → {r['qtd_leis']} leis")

    con.close()


# =============================================================================
# PONTO DE ENTRADA
# =============================================================================

if __name__ == '__main__':
    log.info("=" * 60)
    log.info("FOPAG — Migração de Dados")
    log.info(f"Origem:  {XLSX_PATH.name}")
    log.info(f"Destino: {DB_PATH}")
    log.info("=" * 60)

    # Passo 1: Carregar planilha
    df = carregar_planilha()

    # Passo 2: Identificar colunas de leis
    cols_lei = identificar_colunas_leis(df)

    # Passo 3: Migrar para o SQLite
    stats = migrar_para_sqlite(df, cols_lei)

    # Passo 4: Verificar integridade
    verificar_migracao()

    log.info(f"\nLog completo salvo em: {LOG_PATH}")
    sys.exit(0 if stats['cargos_erro'] == 0 else 1)
