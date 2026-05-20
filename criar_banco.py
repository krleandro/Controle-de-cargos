"""
FOPAG — Criação e migração do banco de dados
Execute uma vez antes de iniciar o sistema:  python criar_banco.py

Este script:
  1. Cria o arquivo quadro_pessoal.db com todas as tabelas e view
  2. Importa todos os cargos e leis da planilha xlsx legada
"""

import sqlite3, pandas as pd, re, os, sys
from pathlib import Path

BASE_DIR  = Path(__file__).parent
DB_PATH   = BASE_DIR / "quadro_pessoal.db"
XLSX_PATH = BASE_DIR / "CARGOS EFETIVOS E COMISSIONADOS - PMM - Ativos e extintos - 2026.xlsx"

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA encoding = 'UTF-8';

CREATE TABLE IF NOT EXISTS Cargos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                TEXT    NOT NULL,
    codigo_fopag        TEXT,
    situacao            TEXT    NOT NULL DEFAULT 'Em vigor'
                                CHECK (situacao IN ('Em vigor','Extinto','Revogado')),
    situacao_delib      TEXT    NOT NULL DEFAULT 'não enviado'
                                CHECK (situacao_delib IN ('Enviado','salvo - em revisão','não enviado')),
    tipo_provimento     TEXT    NOT NULL
                                CHECK (tipo_provimento IN ('Efetivo','Comissão','Eletivo')),
    escolaridade        TEXT,
    carga_horaria       TEXT,
    simbolo_vencimento  TEXT,
    total_previstos     INTEGER NOT NULL DEFAULT 0 CHECK (total_previstos >= 0),
    total_ocupados      INTEGER NOT NULL DEFAULT 0 CHECK (total_ocupados >= 0),
    atribuicoes         TEXT,
    recrutamento        TEXT,
    restricao_exigencia TEXT,
    fonte_carga_horaria TEXT,
    fonte_atribuicoes   TEXT,
    criado_em           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    atualizado_em       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_cargos_situacao ON Cargos (situacao);
CREATE INDEX IF NOT EXISTS idx_cargos_tipo     ON Cargos (tipo_provimento);

CREATE TABLE IF NOT EXISTS FontesCargaHoraria (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    cargo_id  INTEGER NOT NULL REFERENCES Cargos (id) ON DELETE CASCADE,
    tipo      TEXT NOT NULL CHECK (tipo IN ('Lei','Edital','Decreto','Outro')),
    numero    TEXT,
    ano       INTEGER,
    detalhes  TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_fch_cargo ON FontesCargaHoraria (cargo_id);

CREATE TABLE IF NOT EXISTS LeisPertinentes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cargo_id       INTEGER NOT NULL REFERENCES Cargos (id) ON DELETE CASCADE,
    numero         TEXT    NOT NULL,
    ano            INTEGER,
    descricao      TEXT,
    acao           TEXT    NOT NULL
                           CHECK (acao IN ('Cria','Extingue','Fixa','Altera','Regulamenta','Outro')),
    quantidade     INTEGER DEFAULT NULL,
    texto_original TEXT,
    criado_em      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_lp_cargo ON LeisPertinentes (cargo_id);
CREATE INDEX IF NOT EXISTS idx_lp_acao  ON LeisPertinentes (acao);

CREATE VIEW IF NOT EXISTS vw_SaldoVagas AS
SELECT
    id, nome, codigo_fopag, situacao, situacao_delib, tipo_provimento,
    escolaridade, carga_horaria, simbolo_vencimento,
    total_previstos, total_ocupados,
    (total_previstos - total_ocupados) AS saldo_vagas,
    CASE WHEN (total_previstos - total_ocupados) < 0 THEN 1 ELSE 0 END AS alerta_saldo_negativo,
    atribuicoes, criado_em, atualizado_em,
    recrutamento, restricao_exigencia, fonte_carga_horaria, fonte_atribuicoes
FROM Cargos;

CREATE TRIGGER IF NOT EXISTS trg_cargos_atualizado_em
AFTER UPDATE ON Cargos FOR EACH ROW
BEGIN
    UPDATE Cargos SET atualizado_em = datetime('now','localtime') WHERE id = OLD.id;
END;
"""

COLUNAS_PRINCIPAIS = {
    'Cargo','Situação','Código FOPAG','Tipo de Provimento',
    'Recrutamento','Restrição - Exigência','Carga Horária Semanal',
    'Fonte Carga Horária','Símbolo de Vencimento',
    'Total de cargos PREVISTOS','Total de cargos OCUPADOS',
    'SALDO TOTAL','Atribuições','Coluna1',
}

def parsear_celula_lei(texto):
    if not isinstance(texto, str) or not texto.strip():
        return {'acao': 'Outro', 'quantidade': None}
    t = texto.strip()
    for pat, acao in [(r'^Cria\s+\+?(\d+)', 'Cria'),
                      (r'^Extingue\s+(\d+)', 'Extingue'),
                      (r'^Fixa\s+(?:em\s+)?(\d+)', 'Fixa')]:
        m = re.match(pat, t, re.I)
        if m: return {'acao': acao, 'quantidade': int(m.group(1))}
    m = re.search(r'Totaliza\s+(\d+)', t, re.I)
    if m: return {'acao': 'Fixa', 'quantidade': int(m.group(1))}
    m = re.match(r'^Aumenta\s+para\s+(\d+)', t, re.I)
    if m: return {'acao': 'Fixa', 'quantidade': int(m.group(1))}
    if re.match(r'^Altera', t, re.I): return {'acao': 'Altera', 'quantidade': None}
    if re.match(r'^(Regulamenta|Plano\s+de)', t, re.I): return {'acao': 'Regulamenta', 'quantidade': None}
    return {'acao': 'Outro', 'quantidade': None}

def extrair_numero_ano_lei(cab):
    m = re.match(r'^[\w\s\.]*?(\d[\d\.]*)/([\d]{2,4})', cab.strip())
    if m:
        num = m.group(1).replace('.', '')
        ano = int(m.group(2))
        if len(m.group(2)) == 2:
            ano = 1900 + ano if ano >= 90 else 2000 + ano
        return num, ano
    return cab[:50], None

def str_ou_none(v):
    if pd.isna(v): return None
    s = str(v).strip()
    return None if s in ('', 'nan', 'NaN', 'None') else s

def sanitizar_int(v, d=0):
    try: return int(float(str(v))) if not pd.isna(v) else d
    except: return d

def sanitizar_carga(v):
    if pd.isna(v): return None
    s = str(v).strip()
    m = re.search(r'\b(\d+)\b', s)
    if m and m.group(1) in {'10','20','25','30','40','44'}: return m.group(1)
    if s in ('Não regulamentada em lei', 'Verificar edital'): return s
    return None

def sanitizar_sit(v):
    if pd.isna(v): return 'Em vigor'
    return {'Em vigor':'Em vigor','Extinto':'Extinto','Extintos':'Extinto',
            'Revogado':'Revogado'}.get(str(v).strip(), 'Em vigor')

def sanitizar_tipo(v):
    if pd.isna(v): return 'Efetivo'
    return {'Efetivo':'Efetivo','Comissão':'Comissão','Comissao':'Comissão',
            'Eletivo':'Eletivo'}.get(str(v).strip(), 'Efetivo')

def parsear_fonte(texto):
    if not isinstance(texto, str) or not texto.strip(): return []
    fontes = []
    for parte in re.split(r'\s+e\s+|\s*/\s*', texto, flags=re.I):
        parte = parte.strip()
        if not parte: continue
        m = re.search(r'Lei\s+(?:Federal\s+)?(?:nº\s*)?(\d[\d\.]*)/(\d{2,4})', parte, re.I)
        if m:
            num = m.group(1).replace('.', '')
            ano = int(m.group(2))
            if len(m.group(2)) == 2: ano = 1900 + ano if ano >= 90 else 2000 + ano
            fontes.append({'tipo': 'Lei', 'numero': num, 'ano': ano, 'detalhes': parte}); continue
        m2 = re.search(r'Edital\s+(\d+)', parte, re.I)
        if m2:
            fontes.append({'tipo': 'Edital', 'numero': m2.group(1), 'ano': None, 'detalhes': parte}); continue
        fontes.append({'tipo': 'Outro', 'numero': None, 'ano': None, 'detalhes': parte})
    return fontes

# ── MAIN ──────────────────────────────────────────────────────────────────────

print("=" * 52)
print("  FOPAG — Criação do Banco de Dados")
print("=" * 52)

# Passo 1: Verificar planilha
if not XLSX_PATH.exists():
    print(f"\n[ERRO] Planilha não encontrada:\n  {XLSX_PATH}")
    print("Coloque a planilha na mesma pasta deste script.")
    sys.exit(1)

# Passo 2: Criar / recriar banco
if DB_PATH.exists():
    resp = input(f"\nBanco já existe ({DB_PATH.stat().st_size // 1024} KB). Recriar? (s/N): ").strip().lower()
    if resp != 's':
        print("Operação cancelada.")
        sys.exit(0)
    DB_PATH.unlink()
    print("Banco anterior removido.")

print("\n[1/3] Criando schema do banco...")
con = sqlite3.connect(DB_PATH)
con.executescript(SCHEMA)
con.commit()
print("      Tabelas, view e trigger criados.")

# Passo 3: Migração
print("\n[2/3] Lendo planilha...")
df = pd.read_excel(XLSX_PATH, sheet_name='Planilha1', dtype=str)
df = df[df['Cargo'].notna() & (df['Cargo'].str.strip() != '')].reset_index(drop=True)
cols_lei = [c for c in df.columns if c not in COLUNAS_PRINCIPAIS]
print(f"      {len(df)} cargos | {len(cols_lei)} colunas de leis")

print("\n[3/3] Importando dados...")
stats = dict(cargos=0, fontes=0, leis=0, erros=0, alertas=0)

for idx, row in df.iterrows():
    try:
        # Determina se a planilha fornece valores quantitativos explícitos
        prev_planilha = row.get('Total de cargos PREVISTOS')
        ocup_planilha = row.get('Total de cargos OCUPADOS')
        tem_dados_planilha = pd.notna(prev_planilha) and str(prev_planilha).strip() not in ('', 'nan')

        cur = con.execute("""
            INSERT INTO Cargos
              (nome, codigo_fopag, situacao, situacao_delib, tipo_provimento, escolaridade,
               carga_horaria, simbolo_vencimento, total_previstos, total_ocupados, atribuicoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            str(row.get('Cargo', '')).strip(),
            str_ou_none(row.get('Código FOPAG')),
            sanitizar_sit(row.get('Situação')),
            'não enviado',                                                 # padrão; editável na UI
            sanitizar_tipo(row.get('Tipo de Provimento')),
            str_ou_none(row.get('Restrição - Exigência')),
            sanitizar_carga(row.get('Carga Horária Semanal')),
            str_ou_none(row.get('Símbolo de Vencimento')),
            sanitizar_int(prev_planilha, 0) if tem_dados_planilha else 0,  # calculado abaixo se vazio
            sanitizar_int(ocup_planilha, 0),
            str_ou_none(row.get('Atribuições')),
        ))
        cargo_id = cur.lastrowid
        stats['cargos'] += 1

        # Fontes de carga horária
        fonte_txt = row.get('Fonte Carga Horária', '')
        for f in parsear_fonte(str(fonte_txt) if pd.notna(fonte_txt) else ''):
            con.execute(
                "INSERT INTO FontesCargaHoraria (cargo_id,tipo,numero,ano,detalhes) VALUES (?,?,?,?,?)",
                (cargo_id, f['tipo'], f['numero'], f['ano'], f['detalhes'])
            )
            stats['fontes'] += 1

        # Leis (colunas pivoteadas da planilha)
        # Acumula total_previstos pelo histórico legislativo quando a planilha
        # não fornece o valor explicitamente (motor: Cria +, Extingue -, Fixa =).
        total_previstos_leis = 0
        for col in cols_lei:
            val = row.get(col)
            if pd.isna(val) or str(val).strip() in ('', 'nan'): continue
            txt = str(val).strip()
            num, ano = extrair_numero_ano_lei(col)
            p = parsear_celula_lei(txt)
            qtd = p['quantidade'] if p['acao'] in ('Cria', 'Extingue', 'Fixa') else None
            con.execute(
                "INSERT INTO LeisPertinentes "
                "(cargo_id,numero,ano,descricao,acao,quantidade,texto_original) VALUES (?,?,?,?,?,?,?)",
                (cargo_id, num, ano, col[:200], p['acao'], qtd, txt[:500])
            )
            stats['leis'] += 1

            # Motor de saldo
            if p['acao'] == 'Cria' and qtd:
                total_previstos_leis += qtd
            elif p['acao'] == 'Extingue' and qtd:
                total_previstos_leis = max(0, total_previstos_leis - qtd)
            elif p['acao'] == 'Fixa' and qtd:
                total_previstos_leis = qtd

        # Se a planilha não tinha valor, usa o calculado pelo histórico de leis
        if not tem_dados_planilha and total_previstos_leis > 0:
            con.execute(
                "UPDATE Cargos SET total_previstos=? WHERE id=?",
                (total_previstos_leis, cargo_id)
            )
            stats['prev_calculados'] = stats.get('prev_calculados', 0) + 1

        total_prev_final = sanitizar_int(prev_planilha, 0) if tem_dados_planilha else total_previstos_leis
        total_ocup_final = sanitizar_int(ocup_planilha, 0)
        if total_prev_final - total_ocup_final < 0:
            stats['alertas'] += 1

    except Exception as e:
        stats['erros'] += 1
        print(f"  [aviso] Linha {idx+2}: {str(row.get('Cargo','?'))[:40]} — {e}")

con.commit()

# Verificação final
r = con.execute(
    "SELECT COUNT(*), SUM(saldo_vagas), SUM(alerta_saldo_negativo) FROM vw_SaldoVagas"
).fetchone()
con.close()

print()
print("=" * 52)
print("  CONCLUÍDO")
print(f"  ✔ Cargos:                    {stats['cargos']}")
print(f"  ✔ Leis vinculadas:           {stats['leis']}")
print(f"  ✔ Fontes de C.H.:            {stats['fontes']}")
print(f"  ✔ Previstos via leis:        {stats.get('prev_calculados', 0)}  (planilha sem valor)")
print(f"  ⚠ Alertas (saldo<0):         {stats['alertas']}")
print(f"  ✗ Erros:                     {stats['erros']}")
print(f"\n  Banco: {DB_PATH.name}  ({DB_PATH.stat().st_size // 1024} KB)")
print(f"  Verificação: {r[0]} cargos, saldo geral: {r[1]}, alertas: {r[2]}")
print("=" * 52)
print("\nBanco criado com sucesso! Execute iniciar.bat para abrir o sistema.")
